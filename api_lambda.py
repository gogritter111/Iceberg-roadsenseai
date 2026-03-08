"""
RoadSense AI — API Lambda (api_lambda.py)
Serves incident data from DynamoDB to the React dashboard via API Gateway.

Routes:
  GET  /incidents          → list all active incidents (sorted by confidence, newest first)
  GET  /incidents/{id}     → single incident detail with signals
  POST /ingest-signal      → accept a signal directly (used for live demo)

Trigger: API Gateway REST API
Owner: Srikar (deploy + IAM), Durva (this file)

Required IAM permissions on Lambda role:
  - dynamodb:Scan on roadsense-incidents
  - dynamodb:GetItem on roadsense-incidents
  - dynamodb:PutItem on roadsense-signals (for POST /ingest-signal)
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ── Config ────────────────────────────────────────────────────────────────────

AWS_REGION      = os.environ.get("AWS_REGION",       "us-east-1")
INCIDENTS_TABLE = os.environ.get("INCIDENTS_TABLE",   "roadsense-incidents")
SIGNALS_TABLE   = os.environ.get("SIGNALS_TABLE",     "roadsense-signals")

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
incidents_table = dynamodb.Table(INCIDENTS_TABLE)
signals_table   = dynamodb.Table(SIGNALS_TABLE)

# CORS headers — required so the React CloudFront dashboard can call this
CORS_HEADERS = {
    "Content-Type":                 "application/json",
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


# ── Decimal serialisation ─────────────────────────────────────────────────────

class DecimalEncoder(json.JSONEncoder):
    """DynamoDB returns Decimals — convert to float for JSON."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def to_json(obj) -> str:
    return json.dumps(obj, cls=DecimalEncoder)


# ── GET /incidents ────────────────────────────────────────────────────────────

def get_incidents(query_params: dict) -> dict:
    """
    Return all incidents from DynamoDB, sorted by confidence descending.
    Optional query params:
      ?status=active        filter by status (default: all)
      ?limit=20             max results (default: 50)
      ?damage_type=pothole  filter by damage type
    """
    status      = (query_params or {}).get("status")
    limit       = int((query_params or {}).get("limit", 50))
    damage_type = (query_params or {}).get("damage_type")

    try:
        # Scan the incidents table — small dataset at hackathon scale
        scan_kwargs = {}
        filters = []

        if status:
            filters.append(Attr("status").eq(status))
        if damage_type:
            filters.append(Attr("damage_type").eq(damage_type))

        if filters:
            combined = filters[0]
            for f in filters[1:]:
                combined = combined & f
            scan_kwargs["FilterExpression"] = combined

        response  = incidents_table.scan(**scan_kwargs)
        incidents = response.get("Items", [])

        # Handle pagination for large tables
        while "LastEvaluatedKey" in response:
            scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            response  = incidents_table.scan(**scan_kwargs)
            incidents.extend(response.get("Items", []))

        # Sort by confidence_score descending, then created_at descending
        incidents.sort(
            key=lambda x: (
                float(x.get("confidence_score", 0)),
                x.get("created_at", "")
            ),
            reverse=True
        )

        # Apply limit
        incidents = incidents[:limit]

        logger.info(f"[API] GET /incidents → {len(incidents)} incidents returned")

        return {
            "statusCode": 200,
            "headers":    CORS_HEADERS,
            "body":       to_json({
                "count":     len(incidents),
                "incidents": incidents,
            }),
        }

    except Exception as e:
        logger.error(f"[API] GET /incidents failed: {e}")
        return {
            "statusCode": 500,
            "headers":    CORS_HEADERS,
            "body":       to_json({"error": str(e)}),
        }


# ── GET /incidents/{id} ───────────────────────────────────────────────────────

def get_incident_by_id(incident_id: str) -> dict:
    """Return a single incident by ID."""
    try:
        response = incidents_table.get_item(Key={"incident_id": incident_id})
        incident = response.get("Item")

        if not incident:
            return {
                "statusCode": 404,
                "headers":    CORS_HEADERS,
                "body":       to_json({"error": f"Incident {incident_id} not found"}),
            }

        logger.info(f"[API] GET /incidents/{incident_id} → found")

        return {
            "statusCode": 200,
            "headers":    CORS_HEADERS,
            "body":       to_json({"incident": incident}),
        }

    except Exception as e:
        logger.error(f"[API] GET /incidents/{incident_id} failed: {e}")
        return {
            "statusCode": 500,
            "headers":    CORS_HEADERS,
            "body":       to_json({"error": str(e)}),
        }


# ── POST /ingest-signal ───────────────────────────────────────────────────────

def post_ingest_signal(body: dict) -> dict:
    """
    Accept a signal directly via API — used for the live demo.
    Writes to roadsense-signals DynamoDB table.
    DynamoDB Stream fires the Ingest Lambda automatically.

    Minimal required fields:
      signal_id, original_content, source, source_name, city
    """
    try:
        signal_id = body.get("signal_id") or str(uuid.uuid4())
        content   = body.get("original_content", "").strip()

        if not content:
            return {
                "statusCode": 400,
                "headers":    CORS_HEADERS,
                "body":       to_json({"error": "original_content is required"}),
            }

        now = datetime.now(timezone.utc).isoformat()

        item = {
            "signal_id":          signal_id,
            "original_content":   content,
            "translated_content": body.get("translated_content", ""),
            "detected_language":  body.get("detected_language", ""),
            "source":             body.get("source", "api"),
            "source_name":        body.get("source_name", "direct_ingest"),
            "city":               body.get("city", "Bangalore"),
            "timestamp":          body.get("timestamp", now),
            "created_at":         now,
            "location":           body.get("location", {
                "coordinates":    {"lat": Decimal("12.9716"), "lon": Decimal("77.5946")},
                "accuracy_meters": 5000,
                "address":        body.get("city", "Bangalore"),
            }),
        }

        # Remove empty strings — DynamoDB rejects them
        item = {k: v for k, v in item.items() if v != ""}

        signals_table.put_item(Item=item)

        logger.info(f"[API] POST /ingest-signal → {signal_id} written to DynamoDB")

        return {
            "statusCode": 200,
            "headers":    CORS_HEADERS,
            "body":       to_json({
                "signal_id": signal_id,
                "status":    "accepted",
                "message":   "Signal written to DynamoDB. Ingest Lambda will process via Stream.",
            }),
        }

    except Exception as e:
        logger.error(f"[API] POST /ingest-signal failed: {e}")
        return {
            "statusCode": 500,
            "headers":    CORS_HEADERS,
            "body":       to_json({"error": str(e)}),
        }


# ── Router ────────────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    """
    API Gateway REST API event router.

    Supported routes:
      OPTIONS *              → CORS preflight
      GET  /incidents        → list incidents
      GET  /incidents/{id}   → single incident
      POST /ingest-signal    → write a new signal
    """
    method = event.get("httpMethod", "GET")
    path   = event.get("path", "/incidents")
    params = event.get("queryStringParameters") or {}

    logger.info(f"[API] {method} {path}")

    # CORS preflight
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    # GET /incidents/{id}
    if method == "GET" and event.get("pathParameters", {}) and \
       event["pathParameters"].get("id"):
        return get_incident_by_id(event["pathParameters"]["id"])

    # GET /incidents
    if method == "GET" and "/incidents" in path:
        return get_incidents(params)

    # POST /ingest-signal
    if method == "POST" and "/ingest-signal" in path:
        try:
            body = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            return {
                "statusCode": 400,
                "headers":    CORS_HEADERS,
                "body":       to_json({"error": "Invalid JSON body"}),
            }
        return post_ingest_signal(body)

    return {
        "statusCode": 404,
        "headers":    CORS_HEADERS,
        "body":       to_json({"error": f"Route not found: {method} {path}"}),
    }
