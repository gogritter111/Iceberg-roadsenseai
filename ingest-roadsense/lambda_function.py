"""
RoadSense AI — Ingest Lambda (ingest_lambda.py)
Triggered by DynamoDB Streams whenever scraper_lambda writes a new signal.
Embeds the translated content via Amazon Bedrock (Titan) and stores
the vector + metadata in ChromaDB. Also writes the enriched signal to S3
to trigger the downstream Inference Lambda.

Trigger:  DynamoDB Stream on roadsense-signals table (NEW_IMAGE)
Next step: Inference Lambda (triggered by S3 ObjectCreated on roadsense-raw-signals-*)
Owner: Srikar (IAM), rest of team for downstream agents
"""

import json
import logging
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ── Config ────────────────────────────────────────────────────────────────────

CHROMA_HOST    = os.environ.get("CHROMA_HOST",    "98.80.183.42")
CHROMA_PORT    = os.environ.get("CHROMA_PORT",    "8000")
TENANT         = "default_tenant"
DATABASE       = "default_database"
COLLECTION_ID  = "9c0d4b37-ec84-4e00-bf45-018feced81d6"

BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "us-east-1")
EMBED_MODEL_ID = os.environ.get("EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")

S3_BUCKET      = os.environ.get("S3_BUCKET", "roadsense-raw-signals-778277577994")
S3_PREFIX      = "signals/"

bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
s3      = boto3.client("s3")


# ── DynamoDB Stream Parsing ───────────────────────────────────────────────────

def parse_stream_record(record: dict) -> dict | None:
    """
    Extract the signal dict from a DynamoDB Stream NEW_IMAGE record.
    DynamoDB serialises all values as { "S": "...", "N": "...", "M": {...} } etc.
    boto3's TypeDeserializer handles the unwrapping for us.
    Returns the plain signal dict, or None if this isn't an INSERT event.
    """
    # Only process INSERT events — ignore MODIFY and REMOVE
    if record.get("eventName") != "INSERT":
        logger.debug(f"[Stream] Skipping non-INSERT event: {record.get('eventName')}")
        return None

    new_image = record.get("dynamodb", {}).get("NewImage")
    if not new_image:
        logger.warning("[Stream] INSERT record has no NewImage — skipping")
        return None

    from boto3.dynamodb.types import TypeDeserializer
    deserializer = TypeDeserializer()

    try:
        signal = {k: deserializer.deserialize(v) for k, v in new_image.items()}
        return signal
    except Exception as e:
        logger.error(f"[Stream] Failed to deserialise DynamoDB record: {e}")
        return None


# ── Validation ────────────────────────────────────────────────────────────────

def validate_signal(signal: dict):
    """
    Signals from DynamoDB always use the new format (signal_id + translated_content).
    Legacy id/text format kept for safety in case of direct test invocations.
    """
    has_new    = signal.get("signal_id") and signal.get("translated_content")
    has_legacy = signal.get("id") and signal.get("text")

    if not has_new and not has_legacy:
        raise ValueError(
            "Missing required fields: need ('signal_id' + 'translated_content') "
            "or ('id' + 'text')"
        )

    if has_new:
        if not isinstance(signal["signal_id"], str) or not signal["signal_id"].strip():
            raise ValueError("'signal_id' must be a non-empty string")
        if not isinstance(signal["translated_content"], str) or not signal["translated_content"].strip():
            raise ValueError("'translated_content' must be a non-empty string")
    else:
        if not isinstance(signal["text"], str) or not signal["text"].strip():
            raise ValueError("'text' must be a non-empty string")
        if not isinstance(signal["id"], str) or not signal["id"].strip():
            raise ValueError("'id' must be a non-empty string")


def extract_fields(signal: dict) -> tuple[str, str, dict]:
    """Extract (doc_id, text_to_embed, chroma_metadata) from signal."""
    if signal.get("signal_id"):
        doc_id = signal["signal_id"].strip()
        text   = signal["translated_content"].strip()

        location = signal.get("location") or {}
        # location may be a JSON string from DynamoDB or a dict
        if isinstance(location, str):
            try:
                location = json.loads(location)
            except:
                location = {}
        coords   = location.get("coordinates") or {}

        metadata = {
            "signal_type":       signal.get("signal_type", ""),
            "original_content":  signal.get("original_content", ""),
            "detected_language": signal.get("detected_language", ""),
            "source":            signal.get("source", ""),
            "source_name":       signal.get("source_name", ""),
            "timestamp":         signal.get("timestamp", ""),
            "city":              signal.get("city", ""),
            "latitude":          float(coords.get("lat", 0.0)),
            "longitude":         float(coords.get("lon", 0.0)),
            "accuracy_meters":   int(location.get("accuracy_meters") or 0),
            "address":           location.get("address", ""),
        }
        # ChromaDB rejects None values in metadata
        metadata = {k: v for k, v in metadata.items() if v is not None}

    else:
        # Legacy format
        doc_id   = signal["id"].strip()
        text     = signal["text"].strip()
        metadata = signal.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}

    return doc_id, text, metadata


# ── Embedding ─────────────────────────────────────────────────────────────────

def embed_text(text: str) -> list[float]:
    response = bedrock.invoke_model(
        modelId=EMBED_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({"inputText": text}),
    )
    result    = json.loads(response["body"].read())
    embedding = result.get("embedding")
    if not embedding or len(embedding) != 1024:
        raise ValueError(
            f"Unexpected embedding dimension: {len(embedding) if embedding else 'None'}")
    return embedding


# ── ChromaDB ──────────────────────────────────────────────────────────────────

def ingest_to_chroma(doc_id: str, text: str,
                     embedding: list[float], metadata: dict) -> dict:
    url = (
        f"http://{CHROMA_HOST}:{CHROMA_PORT}/api/v2"
        f"/tenants/{TENANT}/databases/{DATABASE}"
        f"/collections/{COLLECTION_ID}/add"
    )

    payload = json.dumps({
        "ids":        [doc_id],
        "documents":  [text],
        "embeddings": [embedding],
        "metadatas":  [metadata if metadata else {}],
    }).encode("utf-8")

    req = urllib.request.Request(
        url=url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept":       "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {"status": "inserted"}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ChromaDB HTTP {e.code}: {error_body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"ChromaDB connection failed: {e.reason}") from e


# ── S3 Write (fires Inference Lambda) ────────────────────────────────────────

def write_to_s3(doc_id: str, signal: dict) -> str:
    """
    Write the enriched signal to S3.
    S3 ObjectCreated event triggers the Inference Lambda automatically.
    Returns the S3 key.
    """
    # Parse JSON strings back to dicts for downstream processing
    if isinstance(signal.get("location"), str):
        try:
            signal["location"] = json.loads(signal["location"])
        except:
            signal["location"] = {}
    if isinstance(signal.get("weather_data"), str):
        try:
            signal["weather_data"] = json.loads(signal["weather_data"])
        except:
            pass
    
    enriched = {
        **signal,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }
    key = f"{S3_PREFIX}{doc_id}.json"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(enriched, default=str).encode("utf-8"),
        ContentType="application/json",
    )
    return key


# ── Per-signal Processing ─────────────────────────────────────────────────────

def process_signal(signal: dict) -> dict:
    """Validate → embed → ChromaDB → S3 for one signal."""
    signal_id = signal.get("signal_id") or signal.get("id") or "unknown"
    try:
        validate_signal(signal)
        doc_id, text, metadata = extract_fields(signal)

        embedding = embed_text(text)
        ingest_to_chroma(doc_id, text, embedding, metadata)
        s3_key    = write_to_s3(doc_id, signal)

        logger.info(f"[Ingest] ✓ {doc_id} → ChromaDB + S3 ({s3_key})")
        return {"id": doc_id, "status": "success", "s3_key": s3_key}

    except ValueError as e:
        logger.warning(f"[Ingest] Validation failed for {signal_id}: {e}")
        return {"id": signal_id, "status": "failed",
                "error": "ValidationError", "message": str(e)}
    except RuntimeError as e:
        logger.error(f"[Ingest] Upstream error for {signal_id}: {e}")
        return {"id": signal_id, "status": "failed",
                "error": "UpstreamError", "message": str(e)}
    except Exception as e:
        logger.error(f"[Ingest] Unexpected error for {signal_id}: {e}")
        return {"id": signal_id, "status": "failed",
                "error": type(e).__name__, "message": str(e)}


# ── Lambda Handler ────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    """
    Entry point — triggered by DynamoDB Stream on roadsense-signals.

    Each stream batch contains one or more records. We process each INSERT
    record independently so one failure never blocks the rest of the batch.

    DynamoDB Stream event shape:
      {
        "Records": [
          {
            "eventName": "INSERT" | "MODIFY" | "REMOVE",
            "dynamodb": {
              "NewImage": { <DynamoDB-typed signal fields> }
            }
          },
          ...
        ]
      }
    """
    # ChromaDB heartbeat
    try:
        urllib.request.urlopen(
            f"http://{CHROMA_HOST}:{CHROMA_PORT}/api/v2/heartbeat", timeout=5)
        logger.info("[Ingest] ChromaDB heartbeat OK")
    except Exception as e:
        logger.error(f"[Ingest] ChromaDB unreachable: {e}")

    records = event.get("Records", [])
    if not records:
        logger.warning("[Ingest] No records in stream event")
        return {"statusCode": 200, "processed": 0}

    results   = []
    for record in records:
        signal = parse_stream_record(record)
        if signal is None:
            continue   # MODIFY / REMOVE — skip
        results.append(process_signal(signal))

    succeeded = [r for r in results if r["status"] == "success"]
    failed    = [r for r in results if r["status"] == "failed"]

    logger.info(
        f"[Ingest] Batch done — "
        f"{len(results)} processed, {len(succeeded)} succeeded, {len(failed)} failed"
    )

    # Returning a non-200 here would cause Lambda to retry the entire batch.
    # We always return 200 and log failures individually to avoid duplicate
    # processing of signals that DID succeed in the same batch.
    return {
        "statusCode": 200,
        "processed":  len(results),
        "succeeded":  len(succeeded),
        "failed":     len(failed),
        "results":    results,
    }