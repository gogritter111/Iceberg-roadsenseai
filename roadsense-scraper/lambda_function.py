"""
RoadSense AI — Scraper Lambda (lambda_function.py)
Orchestrates RSS + Weather scrapers → translation → DynamoDB write.
DynamoDB Streams fires the Ingest Lambda automatically on each new record.

Triggered: Hourly via EventBridge
Next step: ingest_lambda.py (triggered by DynamoDB Stream, NOT invoked directly)
Owner: Srikar

DynamoDB table: roadsense-signals
  Partition key: signal_id (String)
  Stream:        NEW_IMAGE  → triggers Ingest Lambda
  TTL attribute: ttl        → auto-expire signals after 30 days

v2 fixes:
- location stored as DynamoDB Map (not JSON string) so ingest_lambda reads coords directly
- convert_floats applied recursively so no float→Decimal errors
- conditional put (not_exists) prevents duplicate writes across hourly runs
- scraped_at always populated
"""

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

from rss_scraper     import scrape_all_feeds
from weather_scraper import scrape_all_cities as scrape_weather
from translate       import translate_signals

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ── Config ────────────────────────────────────────────────────────────────────

DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE",       "roadsense-signals")
SECRETS_NAME   = os.environ.get("SCRAPER_SECRETS_NAME", "roadsense/scraper-keys")
AWS_REGION     = os.environ.get("AWS_REGION",           "us-east-1")
TTL_DAYS       = 30


# ── Helpers ───────────────────────────────────────────────────────────────────

def convert_floats(obj):
    """Recursively convert floats to Decimal for DynamoDB."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats(i) for i in obj]
    return obj


def strip_nones(obj):
    """Recursively remove None values — DynamoDB rejects null string attributes."""
    if isinstance(obj, dict):
        return {k: strip_nones(v) for k, v in obj.items() if v is not None}
    elif isinstance(obj, list):
        return [strip_nones(i) for i in obj]
    return obj


# ── Secrets Bootstrap ─────────────────────────────────────────────────────────

def load_secrets():
    if os.environ.get("OPENWEATHER_API_KEY"):
        logger.info("[Secrets] Keys already in env — skipping Secrets Manager")
        return
    try:
        client   = boto3.client("secretsmanager", region_name=AWS_REGION)
        response = client.get_secret_value(SecretId=SECRETS_NAME)
        secrets  = json.loads(response["SecretString"])
        for k, v in secrets.items():
            os.environ[k] = v
        logger.info(f"[Secrets] Loaded: {list(secrets.keys())}")
    except Exception as e:
        logger.error(f"[Secrets] Failed to load secrets: {e}")
        logger.warning("[Secrets] API-key-dependent scrapers may return empty results")


# ── Scraper Orchestration ─────────────────────────────────────────────────────

def run_scraper(name: str, fn) -> list[dict]:
    logger.info(f"[Scraper] Starting {name}...")
    try:
        signals = fn()
        logger.info(f"[Scraper] {name} → {len(signals)} signals")
        return signals
    except Exception as e:
        logger.error(f"[Scraper] {name} failed: {e}", exc_info=True)
        return []


def collect_all_signals() -> tuple[list[dict], dict]:
    rss_signals     = run_scraper("RSS",     scrape_all_feeds)
    weather_signals = run_scraper("Weather", scrape_weather)

    all_signals = rss_signals + weather_signals

    seen, unique = set(), []
    for s in all_signals:
        sid = s.get("signal_id")
        if sid and sid not in seen:
            seen.add(sid)
            unique.append(s)

    counts = {
        "rss":          len(rss_signals),
        "weather":      len(weather_signals),
        "total_raw":    len(all_signals),
        "total_unique": len(unique),
    }
    return unique, counts


# ── DynamoDB Write ────────────────────────────────────────────────────────────

def write_signal(table, signal: dict, ttl_ts: int) -> str:
    """
    Write one signal with conditional put to prevent duplicates.
    location stored as DynamoDB Map so ingest_lambda reads coords without json.loads().
    Returns "written" | "duplicate" | "failed"
    """
    signal_id = signal.get("signal_id", "unknown")
    try:
        raw_location = signal.get("location") or {}

        item = {
            "signal_id":          signal_id,
            "source":             signal.get("source", ""),
            "source_name":        signal.get("source_name", ""),
            "original_content":   signal.get("original_content", ""),
            "translated_content": signal.get("translated_content", ""),
            "detected_language":  signal.get("detected_language", "en"),
            "city":               signal.get("city", "Bangalore"),
            "created_at":         signal.get("timestamp", datetime.now(timezone.utc).isoformat()),
            "scraped_at":         datetime.now(timezone.utc).isoformat(),
            "ttl":                ttl_ts,
            # Store as Map — NOT json.dumps() string
            "location":           convert_floats(raw_location),
        }

        if signal.get("weather_data"):
            item["weather_data"] = convert_floats(signal["weather_data"])

        item = strip_nones(item)

        table.put_item(
            Item=item,
            ConditionExpression=Attr("signal_id").not_exists(),
        )
        return "written"

    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            logger.debug(f"[DynamoDB] Duplicate skipped: {signal_id}")
            return "duplicate"
        logger.error(f"[DynamoDB] Write failed for {signal_id}: {e}")
        return "failed"

    except Exception as e:
        logger.error(f"[DynamoDB] Unexpected error for {signal_id}: {e}")
        return "failed"


def write_to_dynamodb(signals: list[dict]) -> dict:
    if not signals:
        return {"written": 0, "duplicates": 0, "failed": 0}

    dynamodb  = boto3.resource("dynamodb", region_name=AWS_REGION)
    table     = dynamodb.Table(DYNAMODB_TABLE)
    ttl_ts    = int((datetime.now(timezone.utc) + timedelta(days=TTL_DAYS)).timestamp())

    written, duplicates, failed = 0, 0, 0
    for signal in signals:
        result = write_signal(table, signal, ttl_ts)
        if result == "written":
            written += 1
        elif result == "duplicate":
            duplicates += 1
        else:
            failed += 1

    logger.info(
        f"[DynamoDB] Done — "
        f"{written} written, {duplicates} duplicates skipped, {failed} failed"
    )
    return {"written": written, "duplicates": duplicates, "failed": failed}


# ── Lambda Handler ────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    """
    Main entry point — triggered hourly by EventBridge.

    Flow:
      1. Load API keys from Secrets Manager
      2. Run RSS + Weather scrapers
      3. Deduplicate
      4. Translate non-English signals
      5. Write to DynamoDB → Stream fires Ingest Lambda per new record
    """
    run_id = datetime.now(timezone.utc).isoformat()
    logger.info(f"[Scraper Lambda] Run started — {run_id}")

    load_secrets()

    signals, scrape_counts = collect_all_signals()
    logger.info(
        f"[Scraper Lambda] Collected — "
        f"RSS: {scrape_counts['rss']}, "
        f"Weather: {scrape_counts['weather']}, "
        f"Unique: {scrape_counts['total_unique']}"
    )

    if signals:
        signals = translate_signals(signals)
        logger.info(f"[Scraper Lambda] Translation done — {len(signals)} signals ready")

    db_counts = write_to_dynamodb(signals)

    return {
        "statusCode": 200,
        "run_id":     run_id,
        "scrape":     scrape_counts,
        "dynamodb":   db_counts,
    }