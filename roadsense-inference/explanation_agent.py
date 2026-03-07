"""
RoadSense AI — Explanation Agent (explanation_agent.py)
Generates human-readable AI summaries of why an incident was flagged.

Model: Claude Sonnet (via bedrock_client.py from Srikar)
Input: incidents from inference_agent.py
Output: same incidents with 'explanation' field populated

Called ONCE per incident (not per signal) — Sonnet is used here for quality prose.
References source types and languages in the summary for demo impact.
"""

import logging
from datetime import datetime, timezone

from bedrock_client import generate

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ── Config ────────────────────────────────────────────────────────────────────

MAX_EXPLANATION_LENGTH = 600   # characters — keeps UI text block manageable

LANGUAGE_NAMES = {
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "kn": "Kannada",
    "bn": "Bengali",
    "mr": "Marathi",
    "ml": "Malayalam",
    "gu": "Gujarati",
    "pa": "Punjabi",
    "ur": "Urdu",
    "en": "English",
}

SOURCE_DISPLAY_NAMES = {
    "reddit":          "Reddit",
    "youtube":         "YouTube",
    "times_of_india":  "Times of India",
    "ndtv":            "NDTV",
    "the_hindu":       "The Hindu",
    "deccan_herald":   "Deccan Herald",
    "hindustan_times": "Hindustan Times",
    "openweathermap":  "weather data",
}


# ── Prompt ────────────────────────────────────────────────────────────────────

def build_signal_summary(signals: list[dict]) -> str:
    """Build a concise summary of signals for the prompt."""
    lines = []

    for s in signals[:8]:   # cap at 8 signals to keep prompt size manageable
        source      = SOURCE_DISPLAY_NAMES.get(s.get("source_name", ""), s.get("source_name", "unknown"))
        lang_code   = s.get("detected_language", "en")
        lang_name   = LANGUAGE_NAMES.get(lang_code, lang_code)
        content     = s.get("translated_content") or s.get("original_content", "")
        content     = content[:120].strip()
        urgency     = s.get("intent", {}).get("urgency_level", "low")

        lang_note = f" [originally in {lang_name}]" if lang_code not in ("en", "unknown", None) else ""
        lines.append(f"- [{source}{lang_note}, urgency={urgency}]: \"{content}\"")

    return "\n".join(lines)


def build_prompt(incident: dict, signals: list[dict]) -> str:
    location      = incident.get("location", {}).get("address", "unknown location")
    damage_type   = incident.get("damage_type", "general").replace("_", " ")
    confidence    = incident.get("confidence_score", 0)
    severity      = incident.get("severity_level", "low")
    source_diversity = incident.get("source_diversity", [])
    signal_count  = incident.get("signal_count", 0)

    # Time range
    signals_sorted = sorted(
        [s for s in signals if s.get("timestamp")],
        key=lambda s: s["timestamp"]
    )
    if signals_sorted:
        earliest = signals_sorted[0]["timestamp"][:10]
        latest   = signals_sorted[-1]["timestamp"][:10]
        time_range = f"{earliest} to {latest}" if earliest != latest else earliest
    else:
        time_range = "recent"

    # Language breakdown
    langs = set()
    for s in signals:
        lang = s.get("detected_language")
        if lang and lang not in ("en", "unknown", None):
            langs.add(LANGUAGE_NAMES.get(lang, lang))
    lang_note = f" Some signals were originally in {', '.join(sorted(langs))}." if langs else ""

    signal_summary = build_signal_summary(signals)

    source_display = [SOURCE_DISPLAY_NAMES.get(s, s) for s in source_diversity]

    return f"""You are an AI system that explains road infrastructure alerts to municipal authorities in India.

An incident has been detected. Write a clear, factual 2-4 sentence explanation of why this incident was flagged.

Incident details:
- Location: {location}
- Damage type: {damage_type}
- Confidence score: {confidence}/100
- Severity: {severity}
- Signal count: {signal_count} signals over {time_range}
- Sources: {', '.join(source_display)}
{lang_note}

Sample signals that contributed to this incident:
{signal_summary}

Write the explanation in plain English for a municipal official (non-technical audience).
Rules:
- 2-4 sentences maximum
- Mention the number and types of sources (e.g. "3 Reddit posts and 1 news article")
- Mention if signals came from non-English languages (e.g. "originally posted in Hindi and Telugu")
- Reference the location and damage type
- Do NOT mention confidence scores or technical terms
- Do NOT use bullet points — write in flowing prose
- Sound factual and neutral, not alarming

Example good explanation:
"Multiple reports of severe waterlogging on NH-65 in Hyderabad were detected across 3 Reddit posts (originally in Hindi and Telugu) and 1 Times of India article over 2 days, coinciding with heavy rainfall recorded by weather monitoring. The reports describe vehicles getting stranded and road surface damage consistent with flooding."

Write only the explanation text. No preamble, no labels."""


# ── Core Agent ────────────────────────────────────────────────────────────────

def explain_incident(incident: dict) -> dict:
    """
    Generate explanation for a single incident.
    Called once per incident.

    Args:
        incident: Incident dict from inference_agent.py with signals embedded

    Returns:
        Same incident with 'explanation' field populated
    """
    signals = incident.get("signals", [])

    # Build fallback explanation in case Claude fails
    fallback = _build_fallback_explanation(incident)

    if not signals:
        logger.warning(f"[Explanation] No signals for incident {incident.get('incident_id', '?')[:8]}")
        incident["explanation"] = fallback
        return incident

    prompt = build_prompt(incident, signals)

    try:
        explanation = generate(prompt)

        # Clean up response
        explanation = explanation.strip()
        if explanation.startswith('"') and explanation.endswith('"'):
            explanation = explanation[1:-1]

        # Truncate if too long
        if len(explanation) > MAX_EXPLANATION_LENGTH:
            explanation = explanation[:MAX_EXPLANATION_LENGTH].rsplit(".", 1)[0] + "."

        incident["explanation"] = explanation

        logger.info(
            f"[Explanation] Generated for incident {incident.get('incident_id', '?')[:8]} "
            f"({len(explanation)} chars)"
        )

    except Exception as e:
        logger.error(f"[Explanation] Claude Sonnet call failed: {e}")
        incident["explanation"] = fallback

    return incident


def _build_fallback_explanation(incident: dict) -> str:
    """Fallback explanation built from structured data — no Claude needed."""
    location     = incident.get("location", {}).get("address", "an unknown location")
    damage_type  = incident.get("damage_type", "road damage").replace("_", " ")
    signal_count = incident.get("signal_count", 0)
    sources      = incident.get("source_diversity", [])
    severity     = incident.get("severity_level", "low")

    source_display = [SOURCE_DISPLAY_NAMES.get(s, s) for s in sources]
    source_str     = ", ".join(source_display) if source_display else "multiple sources"

    return (
        f"{signal_count} signals indicating {damage_type} in {location} were detected "
        f"across {source_str}. The incident has been classified as {severity} severity "
        f"and requires review by the relevant municipal authority."
    )


def explain_incidents(incidents: list[dict]) -> list[dict]:
    """
    Generate explanations for all incidents.

    Args:
        incidents: List of incident dicts from inference_agent.py

    Returns:
        Incidents with explanation fields populated
    """
    for i, incident in enumerate(incidents):
        logger.info(f"[Explanation] Processing incident {i+1}/{len(incidents)}")
        explain_incident(incident)

    logger.info(f"[Explanation] Done — {len(incidents)} explanations generated")
    return incidents


# ── Lambda Handler ────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    """
    Called by Srikar's Inference Lambda after inference_agent.py.
    Returns fully populated incidents ready for DynamoDB storage + API.
    """
    incidents = event.get("incidents", [])

    if not incidents:
        return {"statusCode": 200, "incidents": [], "count": 0}

    explained = explain_incidents(incidents)

    return {
        "statusCode": 200,
        "incidents":  explained,
        "count":      len(explained),
    }


# ── Local Test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import json
    from unittest.mock import MagicMock, patch

    mock_bedrock = MagicMock()
    mock_bedrock.generate.return_value = (
        "Multiple reports of severe potholes on MG Road in Bangalore were detected "
        "across 3 Reddit posts (originally in Hindi and Telugu) and 1 Times of India "
        "article over 2 days. The reports describe vehicle damage and traffic disruption "
        "consistent with large, unfilled potholes in the road surface."
    )
    sys.modules["bedrock_client"] = mock_bedrock

    with patch("__main__.generate", mock_bedrock.generate):

        test_incidents = [
            {
                "incident_id":     "inc-001",
                "signal_ids":      ["s001", "s002", "s003"],
                "signal_count":    3,
                "damage_type":     "pothole",
                "confidence_score": 82,
                "severity_level":  "high",
                "status":          "active",
                "source_diversity": ["reddit", "youtube", "times_of_india"],
                "location": {
                    "center_coordinates": {"lat": 12.9716, "lon": 77.5946},
                    "address": "Bangalore",
                },
                "signals": [
                    {
                        "signal_id": "s001",
                        "source_name": "reddit",
                        "detected_language": "hi",
                        "translated_content": "There is a very big pothole on MG Road near Trinity Circle",
                        "original_content": "MG Road ke paas bahut bada gaddha hai Trinity Circle ke paas",
                        "timestamp": "2026-02-25T10:00:00+00:00",
                        "intent": {"urgency_level": "high"},
                    },
                    {
                        "signal_id": "s002",
                        "source_name": "youtube",
                        "detected_language": "te",
                        "translated_content": "Road full of potholes near MG Road Bangalore, car damaged",
                        "original_content": "MG Road దగ్గర చాలా గుంతలు ఉన్నాయి",
                        "timestamp": "2026-02-26T08:00:00+00:00",
                        "intent": {"urgency_level": "high"},
                    },
                    {
                        "signal_id": "s003",
                        "source_name": "times_of_india",
                        "detected_language": "en",
                        "translated_content": "Potholes on MG Road causing traffic chaos in Bangalore",
                        "original_content": "Potholes on MG Road causing traffic chaos in Bangalore",
                        "timestamp": "2026-02-27T06:00:00+00:00",
                        "intent": {"urgency_level": "high"},
                    },
                ],
            },
            {
                "incident_id":     "inc-002",
                "signal_ids":      ["s004", "s005"],
                "signal_count":    2,
                "damage_type":     "flooding",
                "confidence_score": 71,
                "severity_level":  "high",
                "status":          "active",
                "source_diversity": ["openweathermap", "reddit"],
                "location": {
                    "center_coordinates": {"lat": 19.0760, "lon": 72.8777},
                    "address": "Mumbai",
                },
                "signals": [
                    {
                        "signal_id": "s004",
                        "source_name": "openweathermap",
                        "detected_language": "en",
                        "translated_content": "Weather alert in Mumbai: Heavy rainfall 18mm/hour. Flooding risk.",
                        "original_content": "Weather alert in Mumbai: Heavy rainfall 18mm/hour. Flooding risk.",
                        "timestamp": "2026-02-27T09:00:00+00:00",
                        "intent": {"urgency_level": "medium"},
                    },
                    {
                        "signal_id": "s005",
                        "source_name": "reddit",
                        "detected_language": "en",
                        "translated_content": "Road completely flooded near Dadar, cars stuck",
                        "original_content": "Road completely flooded near Dadar, cars stuck",
                        "timestamp": "2026-02-27T10:00:00+00:00",
                        "intent": {"urgency_level": "critical"},
                    },
                ],
            },
        ]

        print("Testing Explanation Agent...\n")
        results = explain_incidents(test_incidents)

        for inc in results:
            print(f"Incident: {inc['incident_id']}")
            print(f"  Location:    {inc['location']['address']}")
            print(f"  Damage:      {inc['damage_type']}")
            print(f"  Confidence:  {inc['confidence_score']}")
            print(f"  Explanation:")
            print(f"    {inc['explanation']}")
            print()
