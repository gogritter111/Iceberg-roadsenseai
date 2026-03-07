"""
RoadSense AI — Intent & Context Agent (intent_agent.py)
Filters noise, sarcasm, and speculation from road-related signals.
Preserves ambiguous content with lower confidence scores.

Model: Claude Haiku (via bedrock_client.py from Srikar)
Input: classified signals from classification_agent.py
Output: signal with 'intent' field populated

Only runs on signals where classification.is_road_related = True
"""

import json
import logging

from bedrock_client import classify

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ── Config ────────────────────────────────────────────────────────────────────

URGENCY_LEVELS  = ["low", "medium", "high", "critical"]
CONTEXT_TYPES   = ["direct_report", "indirect_mention", "news_article",
                   "weather_alert", "speculation", "sarcasm", "ambiguous"]


# ── Prompt ────────────────────────────────────────────────────────────────────

def build_prompt(text: str, source: str, damage_type: str) -> str:
    return f"""You are an intent classifier for a road infrastructure monitoring system in India.

A signal has already been classified as road-related (damage type: {damage_type}).
Your job is to determine the INTENT behind the text — is this a genuine problem report,
or is it noise, sarcasm, speculation, or an indirect mention?

Source type: {source}
Text to analyze:
\"\"\"{text}\"\"\"

Respond ONLY with a valid JSON object in this exact format:
{{
  "is_problem_report": <true or false>,
  "urgency_level": <"low" | "medium" | "high" | "critical">,
  "context_type": <"direct_report" | "indirect_mention" | "news_article" | "weather_alert" | "speculation" | "sarcasm" | "ambiguous">,
  "confidence_modifier": <float between -0.4 and +0.2>,
  "reasoning": "<one sentence explanation>"
}}

Classification rules:

is_problem_report:
- true  → person is directly reporting or describing an existing road problem
- false → sarcasm, speculation, rhetorical question, general complaint without specifics

urgency_level:
- "critical" → immediate danger, accident reported, road completely blocked
- "high"     → significant damage, vehicle damage reported, multiple complaints
- "medium"   → noticeable damage, inconvenience reported
- "low"      → minor issue, old report, vague mention

context_type:
- "direct_report"    → first-hand account of seeing/experiencing the problem
- "indirect_mention" → heard from someone else, general area mention
- "news_article"     → formal news report about infrastructure
- "weather_alert"    → weather-based road risk signal
- "speculation"      → guessing or predicting a problem might exist
- "sarcasm"          → sarcastic complaint (e.g. 'Oh great, another pothole!')
- "ambiguous"        → unclear intent, could be any of the above

confidence_modifier (applied to classification confidence score):
- Boost  (+0.1 to +0.2): direct first-hand report with location specifics
- Neutral (0.0):          clear report but no location or vague details
- Reduce (-0.1 to -0.2): indirect mention, speculation, ambiguous
- Reduce (-0.3 to -0.4): clear sarcasm, clear non-report

Important notes for Indian social media context:
- Hindi/translated posts often use indirect phrasing — don't penalise for cultural style
- "yaar road toh dekho" (look at this road, friend) = direct_report, not speculation
- Hashtags and emojis don't reduce credibility
- Short posts can still be high-urgency direct reports

Return ONLY the JSON object. No preamble, no explanation outside the JSON."""


# ── Parser ────────────────────────────────────────────────────────────────────

def parse_response(response_text: str) -> dict:
    """Parse Claude's JSON response with fallback."""
    try:
        clean = response_text.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip()
        clean = clean.replace(": +", ": ")
        result = json.loads(clean)

        is_problem_report   = bool(result.get("is_problem_report", True))
        urgency_level       = result.get("urgency_level", "low")
        context_type        = result.get("context_type", "ambiguous")
        confidence_modifier = float(result.get("confidence_modifier", 0.0))
        reasoning           = result.get("reasoning", "")

        # Validate enums
        if urgency_level not in URGENCY_LEVELS:
            urgency_level = "low"
        if context_type not in CONTEXT_TYPES:
            context_type = "ambiguous"

        # Clamp modifier
        confidence_modifier = max(-0.4, min(0.2, confidence_modifier))

        return {
            "is_problem_report":   is_problem_report,
            "urgency_level":       urgency_level,
            "context_type":        context_type,
            "confidence_modifier": confidence_modifier,
            "reasoning":           reasoning,
        }

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning(f"[Intent] Failed to parse response: {e}. Raw: {response_text[:200]}")
        return _fallback_intent()


def _fallback_intent() -> dict:
    """Conservative fallback — treat as ambiguous, no confidence change."""
    return {
        "is_problem_report":   True,
        "urgency_level":       "low",
        "context_type":        "ambiguous",
        "confidence_modifier": 0.0,
        "reasoning":           "Intent classification failed — ambiguous fallback applied",
    }


# ── Core Agent ────────────────────────────────────────────────────────────────

def process_signal(signal: dict) -> dict:
    """
    Run intent classification on a single signal.
    Only processes signals that are road-related.

    Args:
        signal: Signal dict with 'classification' field from classification_agent.py

    Returns:
        Same signal with 'intent' field populated and confidence updated
    """
    classification = signal.get("classification", {})

    # Skip non-road signals — no intent processing needed
    if not classification.get("is_road_related", False):
        signal["intent"] = {
            "is_problem_report":   False,
            "urgency_level":       "low",
            "context_type":        "ambiguous",
            "confidence_modifier": 0.0,
            "reasoning":           "Skipped — not road related",
        }
        return signal

    # Weather signals — pre-process without Claude
    if signal.get("source") == "weather":
        signal["intent"] = {
            "is_problem_report":   True,
            "urgency_level":       "medium",
            "context_type":        "weather_alert",
            "confidence_modifier": 0.0,
            "reasoning":           "Weather signal — pre-classified as weather alert",
        }
        return signal

    # News articles — boost confidence slightly
    if signal.get("source") == "news":
        text        = signal.get("translated_content") or signal.get("original_content", "")
        damage_type = classification.get("damage_type", "general")
        source      = "news_article"
    else:
        text        = signal.get("translated_content") or signal.get("original_content", "")
        damage_type = classification.get("damage_type", "general")
        source      = signal.get("source_name", "social_media")

    if not text.strip():
        signal["intent"] = _fallback_intent()
        return signal

    prompt = build_prompt(text, source, damage_type)

    try:
        response_text = classify(prompt)
        intent = parse_response(response_text)

        # Apply confidence modifier to classification score
        original_confidence = classification.get("confidence", 0.5)
        adjusted_confidence = original_confidence + intent["confidence_modifier"]
        adjusted_confidence = max(0.01, min(0.99, adjusted_confidence))

        # Update the classification confidence in place
        signal["classification"]["confidence"] = adjusted_confidence

        logger.info(
            f"[Intent] signal={signal.get('signal_id', '?')[:8]} "
            f"problem={intent['is_problem_report']} "
            f"urgency={intent['urgency_level']} "
            f"type={intent['context_type']} "
            f"conf={original_confidence:.2f}→{adjusted_confidence:.2f}"
        )

        signal["intent"] = intent

    except Exception as e:
        logger.error(f"[Intent] Claude Haiku call failed: {e}")
        signal["intent"] = _fallback_intent()

    return signal


def process_signals(signals: list[dict]) -> list[dict]:
    """
    Run intent classification on a batch of signals.

    Args:
        signals: List of classified signal dicts

    Returns:
        Signals with intent field populated and confidence scores adjusted
    """
    processed       = []
    problem_count   = 0
    noise_count     = 0

    for signal in signals:
        result = process_signal(signal)
        processed.append(result)

        if result.get("intent", {}).get("is_problem_report"):
            problem_count += 1
        else:
            noise_count += 1

    logger.info(
        f"[Intent] Done — {len(signals)} signals, "
        f"{problem_count} problem reports, {noise_count} noise/non-reports"
    )

    return processed


# ── Lambda Handler ────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    """
    Called by Srikar's Inference Lambda after classification_agent.py.
    """
    signals = event.get("signals", [])

    if not signals:
        return {"statusCode": 200, "signals": [], "count": 0}

    processed = process_signals(signals)

    return {
        "statusCode": 200,
        "signals":    processed,
        "count":      len(processed),
        "problem_report_count": sum(
            1 for s in processed if s.get("intent", {}).get("is_problem_report")
        ),
    }


# ── Local Test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from unittest.mock import MagicMock, patch

    mock_bedrock = MagicMock()
    mock_bedrock.classify.return_value = json.dumps({
        "is_problem_report": True,
        "urgency_level": "high",
        "context_type": "direct_report",
        "confidence_modifier": 0.1,
        "reasoning": "First-hand account with specific location detail."
    })
    sys.modules["bedrock_client"] = mock_bedrock

    with patch("__main__.classify", mock_bedrock.classify):

        test_signals = [
            {
                "signal_id": "test-001",
                "source": "social_media",
                "source_name": "reddit",
                "translated_content": "There is a very big pothole on MG Road, damaged my car",
                "classification": {"is_road_related": True, "damage_type": "pothole", "confidence": 0.92},
            },
            {
                "signal_id": "test-002",
                "source": "social_media",
                "source_name": "reddit",
                "translated_content": "Oh wow, Bangalore roads are SO good, totally no potholes anywhere!",
                "classification": {"is_road_related": True, "damage_type": "pothole", "confidence": 0.65},
            },
            {
                "signal_id": "test-003",
                "source": "news",
                "source_name": "times_of_india",
                "translated_content": "Waterlogging reported on NH-65 after heavy rainfall in Hyderabad",
                "classification": {"is_road_related": True, "damage_type": "flooding", "confidence": 0.88},
            },
            {
                "signal_id": "test-004",
                "source": "weather",
                "source_name": "openweathermap",
                "translated_content": "Weather alert in Mumbai: Heavy rainfall. Potential flooding risk.",
                "classification": {"is_road_related": True, "damage_type": "flooding", "confidence": 0.75},
            },
            {
                "signal_id": "test-005",
                "source": "social_media",
                "source_name": "youtube",
                "translated_content": "I think there might be some road issues near the bridge",
                "classification": {"is_road_related": True, "damage_type": "general", "confidence": 0.45},
            },
        ]

        print("Testing Intent & Context Agent...\n")
        results = process_signals(test_signals)

        for s in results:
            i = s["intent"]
            c = s["classification"]
            print(f"Signal: {s['signal_id']}")
            print(f"  Content:    {s['translated_content'][:60]}")
            print(f"  Problem:    {i['is_problem_report']}")
            print(f"  Urgency:    {i['urgency_level']}")
            print(f"  Context:    {i['context_type']}")
            print(f"  Confidence: {c['confidence']:.2f} (after modifier: {i['confidence_modifier']:+.2f})")
            print(f"  Reasoning:  {i['reasoning']}")
            print()
