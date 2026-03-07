import json
import os
import boto3

# ── Config ────────────────────────────────────────────────────────────────────
BEDROCK_REGION        = os.environ.get("BEDROCK_REGION", "us-east-1")
CLASSIFY_MODEL_ID     = "amazon.nova-micro-v1:0"
CONFIDENCE_THRESHOLD  = 0.7
# ─────────────────────────────────────────────────────────────────────────────

bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)


SYSTEM_PROMPT = """You are a road infrastructure signal classifier for an Indian city monitoring system.

Your job is to determine whether a given piece of text describes a real road-related issue.

Road-related issues include:
- Potholes, road damage, cracks, uneven surfaces
- Waterlogging, flooding on roads
- Traffic signal malfunctions
- Road blockages, accidents, construction
- Broken streetlights, missing road signs
- Landslides or debris on roads

NOT road-related:
- General weather (rain, temperature) with no road impact mentioned
- Political news, sports, entertainment
- Personal opinions unrelated to roads
- Spam, advertisements, gibberish
- Sarcasm or jokes not describing a real issue

Respond ONLY with a valid JSON object, no explanation, no markdown:
{
  "is_road_related": true or false,
  "confidence": a float between 0.0 and 1.0
}"""


def classify_signal(text: str) -> dict:
    """Call Nova Micro to classify a single signal text."""
    body = json.dumps({
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "text": f"{SYSTEM_PROMPT}\n\nClassify this signal:\n\n{text}"
                    }
                ]
            }
        ],
        "inferenceConfig": {
            "maxTokens": 100,
            "temperature": 0,
        }
    })

    response = bedrock.invoke_model(
        modelId=CLASSIFY_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=body,
    )

    raw = json.loads(response["body"].read())
    content = raw.get("output", {}).get("message", {}).get("content", [{}])[0].get("text", "").strip()

    # Strip markdown fences if model wraps response anyway
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    result = json.loads(content)

    if "is_road_related" not in result or "confidence" not in result:
        raise ValueError(f"Unexpected classification response: {content}")

    return {
        "is_road_related": bool(result["is_road_related"]),
        "confidence":      float(result["confidence"]),
    }


def process_signal(signal: dict) -> dict:
    """Classify a single signal. Returns enriched signal or None if discarded."""
    signal_id = signal.get("signal_id") or signal.get("id") or "unknown"
    text      = signal.get("translated_content") or signal.get("text") or ""

    if not text.strip():
        return {"id": signal_id, "status": "discarded", "reason": "empty text"}

    try:
        classification = classify_signal(text)

        # Discard if not road-related or below confidence threshold
        if not classification["is_road_related"] or classification["confidence"] < CONFIDENCE_THRESHOLD:
            return {
                "id":         signal_id,
                "status":     "discarded",
                "reason":     "not road-related",
                "confidence": classification["confidence"],
            }

        # Return enriched signal with classification metadata attached
        enriched = {**signal, "classification": classification}
        return {
            "id":         signal_id,
            "status":     "classified",
            "confidence": classification["confidence"],
            "signal":     enriched,
        }

    except Exception as e:
        return {
            "id":     signal_id,
            "status": "failed",
            "error":  type(e).__name__,
            "message": str(e),
        }


def lambda_handler(event, context):
    """
    Accepts output from the ingest Lambda or direct invocation.
    Input: ingest result body OR a list of signals OR a single signal.
    Output: classified signals ready for the next pipeline stage.
    """
    try:
        # Parse body — handles API Gateway, direct invoke, and raw list
        if isinstance(event, list):
            body = event
        elif isinstance(event.get("body"), str):
            body = json.loads(event["body"])
        elif isinstance(event.get("body"), dict):
            body = event["body"]
        else:
            body = event

        # Accept ingest Lambda output format: {"results": [...]}
        # or a raw list of signals, or a single signal
        if isinstance(body, dict) and "results" in body:
            # Chained from ingest Lambda — extract only succeeded signals
            ingest_results = body["results"]
            signals = [
                r["signal"] for r in ingest_results
                if r.get("status") == "success" and "signal" in r
            ]
            # If ingest didn't attach signal objects, we can't proceed
            if not signals and any(r.get("status") == "success" for r in ingest_results):
                return {
                    "statusCode": 400,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({
                        "error": "ChainError",
                        "message": "Ingest results did not include signal objects. "
                                   "Send signals directly to this Lambda instead.",
                    }),
                }
        elif isinstance(body, list):
            signals = body
        else:
            signals = [body]

        if not signals:
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "processed":  0,
                    "classified": 0,
                    "discarded":  0,
                    "failed":     0,
                    "results":    [],
                }),
            }

        # Classify each signal independently
        results    = [process_signal(s) for s in signals]
        classified = [r for r in results if r["status"] == "classified"]
        discarded  = [r for r in results if r["status"] == "discarded"]
        failed     = [r for r in results if r["status"] == "failed"]

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "processed":  len(results),
                "classified": len(classified),
                "discarded":  len(discarded),
                "failed":     len(failed),
                "results":    results,
            }),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": type(e).__name__, "message": str(e)}),
        }