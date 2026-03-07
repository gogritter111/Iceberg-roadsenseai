"""
from decimal import Decimal

def decimal_to_native(obj):
    if isinstance(obj, Decimal):
        return float(obj) if obj % 1 else int(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_native(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_native(i) for i in obj]
    return obj

RoadSense AI — Inference Lambda (inference_lambda.py)
Triggered by S3 ObjectCreated event when Ingestion Lambda writes a signal.

Pipeline:
  S3 read → normalizer → classification → intent → correlation → inference → explanation → DynamoDB
"""

import json
import os
import logging
from datetime import datetime, timezone

import boto3

# ── Your agent imports ────────────────────────────────────────────────────────
from normalizer            import normalise_signals
from classification_agent  import classify_signals
from intent_agent          import process_signals
from correlation_agent     import cluster_signals
from inference_agent       import process_clusters
from explanation_agent     import explain_incidents
# ─────────────────────────────────────────────────────────────────────────────

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ── Config ────────────────────────────────────────────────────────────────────
S3_BUCKET       = os.environ.get("S3_BUCKET", "roadsense-raw-signals-778277577994")
DYNAMODB_REGION = os.environ.get("DYNAMODB_REGION", "us-east-1")
SIGNALS_TABLE   = os.environ.get("SIGNALS_TABLE", "roadsense-signals")
INCIDENTS_TABLE = os.environ.get("INCIDENTS_TABLE", "roadsense-incidents")
# ─────────────────────────────────────────────────────────────────────────────

s3       = boto3.client("s3")
dynamodb = boto3.resource("dynamodb", region_name=DYNAMODB_REGION)

signals_table   = dynamodb.Table(SIGNALS_TABLE)
incidents_table = dynamodb.Table(INCIDENTS_TABLE)


# ── S3 Reader ─────────────────────────────────────────────────────────────────

def read_signal_from_s3(bucket: str, key: str) -> dict:
    response = s3.get_object(Bucket=bucket, Key=key)
    body     = response["Body"].read().decode("utf-8")
    return json.loads(body)


# ── DynamoDB Writers ──────────────────────────────────────────────────────────

def save_signals(signals: list[dict]):
    with signals_table.batch_writer() as batch:
        for signal in signals:
            item = {
                "signal_id":          signal.get("signal_id", "unknown"),
                "source":             signal.get("source", ""),
                "source_name":        signal.get("source_name", ""),
                "original_content":   signal.get("original_content", ""),
                "translated_content": signal.get("translated_content", ""),
                "detected_language":  signal.get("detected_language", "en"),
                "timestamp":          signal.get("timestamp", ""),
                "ingested_at":        signal.get("ingested_at", ""),
                "saved_at":           datetime.now(timezone.utc).isoformat(),
                "location":           json.dumps(decimal_to_native(signal.get("location", {}))),
                "classification":     json.dumps(decimal_to_native(signal.get("classification", {}))),
                "intent":             json.dumps(decimal_to_native(signal.get("intent", {}))),
            }
            item = {k: v for k, v in item.items() if v != "" and v is not None}
            batch.put_item(Item=item)
    logger.info(f"[Inference Lambda] Saved {len(signals)} signals to DynamoDB")


def save_incidents(incidents: list[dict]):
    with incidents_table.batch_writer() as batch:
        for incident in incidents:
            item = {
                "incident_id":        incident.get("incident_id", "unknown"),
                "cluster_id":         incident.get("cluster_id", ""),
                "damage_type":        incident.get("damage_type", "general"),
                "severity_level":     incident.get("severity_level", "low"),
                "confidence_score":   incident.get("confidence_score", 0),
                "status":             incident.get("status", "active"),
                "explanation":        incident.get("explanation", ""),
                "signal_count":       incident.get("signal_count", 0),
                "signal_ids":         incident.get("signal_ids", []),
                "source_diversity":   incident.get("source_diversity", []),
                "location":           json.dumps(decimal_to_native(incident.get("location", {}))),
                "confidence_history": json.dumps(decimal_to_native(incident.get("confidence_history", []))),
                "created_at":         incident.get("created_at", datetime.now(timezone.utc).isoformat()),
                "updated_at":         incident.get("updated_at", datetime.now(timezone.utc).isoformat()),
            }
            item = {k: v for k, v in item.items() if v != "" and v is not None}
            batch.put_item(Item=item)
    logger.info(f"[Inference Lambda] Saved {len(incidents)} incidents to DynamoDB")


# ── Main Handler ──────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    logger.info(f"[Inference Lambda] Triggered — event: {json.dumps(event)[:500]}")

    # Check if EventBridge scheduled event or S3 event
    is_scheduled = event.get("source") == "aws.events" or (not event.get("Records") and not event.get("s3"))
    
    if is_scheduled:
        logger.info("[Inference Lambda] Scheduled run - loading all signals from DynamoDB")
        # Load all signals from DynamoDB
        try:
            response = signals_table.scan(Limit=100)
            all_items = response.get("Items", [])
            
            all_signals = []
            for item in all_items:
                sig = dict(item)
                for field in ["location", "classification", "intent"]:
                    if field in sig and isinstance(sig[field], str):
                        try:
                            sig[field] = json.loads(sig[field])
                        except Exception:
                            sig[field] = {}
                    elif field not in sig:
                        sig[field] = {}
                all_signals.append(sig)
            
            logger.info(f"[Inference Lambda] Loaded {len(all_signals)} signals for clustering")
            
            if not all_signals:
                return {"statusCode": 200, "message": "No signals to process"}
            
            # Classify and add intent to signals that don't have them
            needs_classification = [s for s in all_signals if not s.get("classification") or not s.get("intent")]
            if needs_classification:
                logger.info(f"[Inference Lambda] Classifying {len(needs_classification)} signals")
                classified = classify_signals(needs_classification)
                classified = process_signals(classified)
                
                # Update in DynamoDB
                with signals_table.batch_writer() as batch:
                    for sig in classified:
                        batch.put_item(Item={
                            "signal_id": sig["signal_id"],
                            "source": sig.get("source", ""),
                            "source_name": sig.get("source_name", ""),
                            "original_content": sig.get("original_content", ""),
                            "translated_content": sig.get("translated_content", ""),
                            "detected_language": sig.get("detected_language", "en"),
                            "city": sig.get("city", ""),
                            "timestamp": sig.get("timestamp", ""),
                            "location": json.dumps(decimal_to_native(sig.get("location", {}))),
                            "classification": json.dumps(decimal_to_native(sig.get("classification", {}))),
                            "intent": json.dumps(decimal_to_native(sig.get("intent", {}))),
                        })
                
                # Update all_signals with classified versions
                sig_map = {s["signal_id"]: s for s in classified}
                for i, sig in enumerate(all_signals):
                    if sig["signal_id"] in sig_map:
                        all_signals[i] = sig_map[sig["signal_id"]]
            
            # Skip to correlation step
            logger.info("[Inference Lambda] Running correlation agent")
            clusters = cluster_signals(all_signals)
            
            if not clusters:
                logger.info("[Inference Lambda] No clusters formed — done")
                return {
                    "statusCode": 200,
                    "signals_processed": len(all_signals),
                    "clusters_formed": 0,
                    "incidents_created": 0,
                }
            
            logger.info("[Inference Lambda] Running inference agent")
            incidents = process_clusters(clusters)
            
            if not incidents:
                logger.info("[Inference Lambda] No incidents met confidence threshold — done")
                return {
                    "statusCode": 200,
                    "signals_processed": len(all_signals),
                    "clusters_formed": len(clusters),
                    "incidents_created": 0,
                }
            
            signal_map = {s["signal_id"]: s for s in all_signals}
            for incident in incidents:
                incident["signals"] = [
                    signal_map[sid]
                    for sid in incident.get("signal_ids", [])
                    if sid in signal_map
                ]
            
            logger.info("[Inference Lambda] Running explanation agent")
            incidents = explain_incidents(incidents)
            
            try:
                save_incidents(incidents)
            except Exception as e:
                logger.error(f"[Inference Lambda] Failed to save incidents: {e}")
            
            logger.info(
                f"[Inference Lambda] Done — "
                f"{len(all_signals)} signals → "
                f"{len(clusters)} clusters → "
                f"{len(incidents)} incidents"
            )
            
            return {
                "statusCode": 200,
                "signals_processed": len(all_signals),
                "clusters_formed": len(clusters),
                "incidents_created": len(incidents),
                "incident_ids": [i["incident_id"] for i in incidents],
            }
            
        except Exception as e:
            logger.error(f"[Inference Lambda] Scheduled run failed: {e}", exc_info=True)
            return {"statusCode": 500, "error": str(e)}
    
    # Original S3-triggered flow
    try:
        records = event.get("Records", [])
        if not records:
            logger.warning("[Inference Lambda] No S3 records in event")
            return {"statusCode": 200, "message": "No records to process"}

        raw_signals = []
        for record in records:
            bucket = record["s3"]["bucket"]["name"]
            key    = record["s3"]["object"]["key"]
            logger.info(f"[Inference Lambda] Reading s3://{bucket}/{key}")
            signal = read_signal_from_s3(bucket, key)
            raw_signals.append(signal)

    except Exception as e:
        logger.error(f"[Inference Lambda] Failed to read from S3: {e}")
        return {"statusCode": 500, "error": str(e)}

    if not raw_signals:
        return {"statusCode": 200, "message": "No signals to process"}

    # ── 2. Normalize the new signal ───────────────────────────────────────────
    logger.info(f"[Inference Lambda] Normalizing {len(raw_signals)} signals")
    new_signals = normalise_signals(raw_signals)

    # ── 3. Classify + Intent on the new signal ────────────────────────────────
    logger.info("[Inference Lambda] Running classification agent")
    new_signals = classify_signals(new_signals)

    logger.info("[Inference Lambda] Running intent agent")
    new_signals = process_signals(new_signals)

    # ── 4. Save new signal to DynamoDB ────────────────────────────────────────
    try:
        save_signals(new_signals)
    except Exception as e:
        logger.error(f"[Inference Lambda] Failed to save signals: {e}")

    # ── 5. Load ALL recent signals from DynamoDB for clustering ───────────────
    logger.info("[Inference Lambda] Loading recent signals from DynamoDB for clustering")
    try:
        response  = signals_table.scan(Limit=100)
        all_items = response.get("Items", [])

        all_signals = []
        for item in all_items:
            sig = dict(item)
            for field in ["location", "classification", "intent"]:
                if field in sig and isinstance(sig[field], str):
                    try:
                        sig[field] = json.loads(sig[field])
                    except Exception:
                        sig[field] = {}
                elif field not in sig:
                    sig[field] = {}
            all_signals.append(sig)
            logger.info(
                f"[Inference Lambda] Loaded signal {sig.get('signal_id')} — "
                f"road={sig.get('classification', {}).get('is_road_related')} "
                f"problem={sig.get('intent', {}).get('is_problem_report')}"
            )

        logger.info(f"[Inference Lambda] Loaded {len(all_signals)} signals for clustering")

    except Exception as e:
        logger.error(f"[Inference Lambda] Failed to load signals from DynamoDB: {e}")
        all_signals = new_signals

    # ── 6. Correlate all signals into clusters ────────────────────────────────
    logger.info("[Inference Lambda] Running correlation agent")
    clusters = cluster_signals(all_signals)

    if not clusters:
        logger.info("[Inference Lambda] No clusters formed — done")
        return {
            "statusCode":        200,
            "signals_processed": len(new_signals),
            "clusters_formed":   0,
            "incidents_created": 0,
        }

    # ── 7. Inference ──────────────────────────────────────────────────────────
    logger.info("[Inference Lambda] Running inference agent")
    incidents = process_clusters(clusters)

    if not incidents:
        logger.info("[Inference Lambda] No incidents met confidence threshold — done")
        return {
            "statusCode":        200,
            "signals_processed": len(new_signals),
            "clusters_formed":   len(clusters),
            "incidents_created": 0,
        }

    # ── 8. Explain ────────────────────────────────────────────────────────────
    signal_map = {s["signal_id"]: s for s in all_signals}
    for incident in incidents:
        incident["signals"] = [
            signal_map[sid]
            for sid in incident.get("signal_ids", [])
            if sid in signal_map
        ]

    logger.info("[Inference Lambda] Running explanation agent")
    incidents = explain_incidents(incidents)

    # ── 9. Save incidents to DynamoDB ─────────────────────────────────────────
    try:
        save_incidents(incidents)
    except Exception as e:
        logger.error(f"[Inference Lambda] Failed to save incidents: {e}")

    logger.info(
        f"[Inference Lambda] Done — "
        f"{len(new_signals)} new signals → "
        f"{len(clusters)} clusters → "
        f"{len(incidents)} incidents"
    )

    return {
        "statusCode":        200,
        "signals_processed": len(new_signals),
        "clusters_formed":   len(clusters),
        "incidents_created": len(incidents),
        "incident_ids":      [i["incident_id"] for i in incidents],
    }