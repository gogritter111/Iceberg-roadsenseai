"""
RoadSense AI — Classification Agent (classification_agent.py)
Determines if a signal is road-related and what type of damage it describes.

Model: Claude Haiku (via bedrock_client.py from Srikar)
Input: translated English text from translate.py
Output: {is_road_related, damage_type, confidence}

Operates on translated English — no language handling needed here.
"""

import json
import logging
from typing import Optional

# bedrock_client.py provided by Srikar
# Functions: get_embedding(text), classify(prompt), generate(prompt)
from bedrock_client import classify

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ── Config ────────────────────────────────────────────────────────────────────

DAMAGE_TYPES = ["pothole", "surface_wear", "flooding", "general"]

# If Claude Haiku returns confidence below this, we still keep the signal
# but flag it as low confidence — never discard ambiguous signals
MIN_CONFIDENCE_THRESHOLD = 0.1


# ── Prompt ────────────────────────────────────────────────────────────────────

def build_prompt(text: str) -> str:
    return f"""You are a road infrastructure signal classifier for an Indian city monitoring system.

Analyze the following text and determine if it describes a road infrastructure problem.

Text to analyze:
\"\"\"{text}\"\"\"

Respond ONLY with a valid JSON object in this exact format:
{{
  "is_road_related": <true or false>,
  "damage_type": <"pothole" | "surface_wear" | "flooding" | "general" | null>,
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<one sentence explanation>"
}}

Classification rules:
- is_road_related: true if the text describes ANY road/highway/street condition, damage, flooding, or infrastructure issue
- damage_type:
    "pothole"      → mentions potholes, craters, holes in road, gaddha, khada
    "surface_wear" → mentions cracks, worn surface, broken asphalt, uneven road
    "flooding"     → mentions waterlogging, road underwater, flood on road
    "general"      → road-related but doesn't fit above categories
    null           → not road related at all
- confidence: how certain you are (0.0 = complete guess, 1.0 = absolutely certain)
    - Lower confidence for sarcasm, speculation, ambiguous language
    - Higher confidence for direct, clear problem reports
    - Never return 0.0 or 1.0 exactly
- Sarcastic or speculative content: set is_road_related based on whether it's about roads,
  but lower the confidence score significantly (0.1–0.4)
- Ambiguous content: do NOT reject — assign lower confidence instead

Return ONLY the JSON object. No preamble, no explanation outside the JSON."""


# ── Parser ────────────────────────────────────────────────────────────────────

def parse_response(response_text: str) -> dict:
    """Parse Claude's JSON response, with fallback for malformed output."""
    try:
        # Strip any accidental markdown fences
        clean = response_text.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip()

        result = json.loads(clean)

        # Validate and sanitise fields
        is_road_related = bool(result.get("is_road_related", False))
        damage_type     = result.get("damage_type", None)
        confidence      = float(result.get("confidence", 0.5))
        reasoning       = result.get("reasoning", "")

        # Clamp confidence to valid range
        confidence = max(0.01, min(0.99, confidence))

        # Validate damage_type enum
        if damage_type not in DAMAGE_TYPES:
            damage_type = "general" if is_road_related else None

        return {
            "is_road_related": is_road_related,
            "damage_type":     damage_type,
            "confidence":      confidence,
            "reasoning":       reasoning,
        }

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning(f"[Classification] Failed to parse response: {e}. Raw: {response_text[:200]}")
        return _fallback_classification()


def _fallback_classification() -> dict:
    """Conservative fallback when Claude's response can't be parsed."""
    return {
        "is_road_related": False,
        "damage_type":     None,
        "confidence":      0.1,
        "reasoning":       "Classification failed — conservative fallback applied",
    }


# ── Core Agent ────────────────────────────────────────────────────────────────

def classify_signal(signal: dict) -> dict:
    """
    Classify a single signal dict.
    Uses translated_content if available, falls back to original_content.

    Args:
        signal: Signal dict from translate.py

    Returns:
        Same signal dict with 'classification' field populated
    """
    # Filter out Mumbai signals
    location = signal.get("location", {})
    if isinstance(location, str):
        import json as json_lib
        try:
            location = json_lib.loads(location)
        except:
            location = {}
    
    address = location.get("address", "")
    if address and "mumbai" in address.lower():
        signal["classification"] = {
            "is_road_related": False,
            "damage_type":     None,
            "confidence":      0.0,
            "reasoning":       "Mumbai location filtered out",
        }
        return signal
    
    # Always use translated English content for classification
    text = signal.get("translated_content") or signal.get("original_content", "")

    if not text or not text.strip():
        logger.warning(f"[Classification] Empty content for signal {signal.get('signal_id')}")
        signal["classification"] = _fallback_classification()
        return signal

    # Weather signals — pre-classify without calling Claude (saves quota)
    if signal.get("source") == "weather":
        signal["classification"] = {
            "is_road_related": True,
            "damage_type":     "flooding",
            "confidence":      0.75,
            "reasoning":       "Weather signal — pre-classified as flooding risk",
        }
        return signal

    prompt = build_prompt(text)

    try:
        response_text = classify(prompt)
        classification = parse_response(response_text)

        logger.info(
            f"[Classification] signal={signal.get('signal_id', '?')[:8]} "
            f"road={classification['is_road_related']} "
            f"type={classification['damage_type']} "
            f"conf={classification['confidence']:.2f}"
        )

        signal["classification"] = classification

    except Exception as e:
        logger.error(f"[Classification] Claude Haiku call failed: {e}")
        signal["classification"] = _fallback_classification()

    return signal


def classify_signals(signals: list[dict]) -> list[dict]:
    """
    Classify a batch of signals.
    Filters out non-road-related signals below confidence threshold.

    Args:
        signals: List of signal dicts from translate.py

    Returns:
        List of signals with classification filled in.
        Non-road signals are kept but flagged — filtering happens in Intent Agent.
    """
    classified = []
    road_count  = 0
    skip_count  = 0

    for signal in signals:
        result = classify_signal(signal)
        classified.append(result)

        if result["classification"]["is_road_related"]:
            road_count += 1
        else:
            skip_count += 1

    logger.info(
        f"[Classification] Done — {len(signals)} signals processed, "
        f"{road_count} road-related, {skip_count} not road-related"
    )

    return classified


# ── Lambda Handler ────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    """
    Called by Srikar's Inference Lambda after translate.py.
    Expects event to contain a 'signals' list.
    """
    signals = event.get("signals", [])

    if not signals:
        return {"statusCode": 200, "signals": [], "count": 0}

    classified = classify_signals(signals)

    return {
        "statusCode": 200,
        "signals":    classified,
        "count":      len(classified),
        "road_related_count": sum(
            1 for s in classified if s["classification"]["is_road_related"]
        ),
    }


# ── Local Test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Mock bedrock_client for local testing without AWS
    import sys
    from unittest.mock import MagicMock

    mock_bedrock = MagicMock()
    mock_bedrock.classify.return_value = json.dumps({
        "is_road_related": True,
        "damage_type": "pothole",
        "confidence": 0.92,
        "reasoning": "Post clearly describes a large pothole causing vehicle damage."
    })
    sys.modules["bedrock_client"] = mock_bedrock

    # Re-import classify with mock in place
    from unittest.mock import patch
    with patch("__main__.classify", mock_bedrock.classify):

        test_signals = [
            {
                "signal_id": "test-001",
                "source": "social_media",
                "original_content": "MG Road par bahut bada gaddha hai",
                "translated_content": "There is a very big pothole on MG Road",
                "detected_language": "hi",
            },
            {
                "signal_id": "test-002",
                "source": "news",
                "original_content": "Flooding on NH-65 after heavy rainfall",
                "translated_content": "Flooding on NH-65 after heavy rainfall",
                "detected_language": "en",
            },
            {
                "signal_id": "test-003",
                "source": "social_media",
                "original_content": "The weather is so nice today in Bangalore!",
                "translated_content": "The weather is so nice today in Bangalore!",
                "detected_language": "en",
            },
            {
                "signal_id": "test-004",
                "source": "weather",
                "original_content": "Weather alert in Mumbai: Heavy rainfall detected.",
                "translated_content": "Weather alert in Mumbai: Heavy rainfall detected.",
                "detected_language": "en",
            },
        ]

        print("Testing Classification Agent...\n")
        results = classify_signals(test_signals)

        for s in results:
            c = s["classification"]
            print(f"Signal: {s['signal_id']}")
            print(f"  Content:    {s['translated_content'][:60]}")
            print(f"  Road:       {c['is_road_related']}")
            print(f"  Type:       {c['damage_type']}")
            print(f"  Confidence: {c['confidence']:.2f}")
            print(f"  Reasoning:  {c['reasoning']}")
            print()
