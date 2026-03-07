"""
RoadSense AI — Inference Agent (inference_agent.py)
Computes confidence score (0–100) and severity level from signal clusters.

Input: clusters from correlation_agent.py
Output: incidents with confidence_score + severity_level

Incident is created only if confidence_score > 60.
Incident is archived if confidence_score drops below 30.

Confidence boosters:
- Source diversity (Reddit + YouTube + news + weather = highest confidence)
- Signal count
- Urgency levels from intent
- Weather correlation
- Recency of signals
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ── Config ────────────────────────────────────────────────────────────────────

INCIDENT_CREATION_THRESHOLD = 30   # confidence must exceed this to create incident
INCIDENT_ARCHIVE_THRESHOLD  = 30   # confidence below this → archive incident

SEVERITY_LEVELS = ["low", "medium", "high", "critical"]

# Source diversity weights — more diverse = higher confidence
SOURCE_WEIGHTS = {
    "reddit":          15,
    "youtube":         12,
    "times_of_india":  18,
    "ndtv":            18,
    "the_hindu":       18,
    "deccan_herald":   16,
    "hindustan_times": 16,
    "openweathermap":  10,
    "unknown":          5,
}

# Urgency level weights from Intent Agent
URGENCY_WEIGHTS = {
    "critical": 20,
    "high":     14,
    "medium":    8,
    "low":       3,
}

# Context type weights
CONTEXT_WEIGHTS = {
    "direct_report":    10,
    "news_article":     12,
    "weather_alert":     6,
    "indirect_mention":  4,
    "ambiguous":         2,
    "speculation":       1,
    "sarcasm":           0,
}


# ── Scoring ───────────────────────────────────────────────────────────────────

def score_source_diversity(cluster: dict) -> float:
    """
    Score based on how many DIFFERENT source types contribute.
    Max 30 points.
    Reddit-only cluster = low score.
    Reddit + YouTube + news + weather = high score.
    """
    sources  = cluster.get("source_diversity", [])
    score    = 0.0

    for source in sources:
        score += SOURCE_WEIGHTS.get(source, SOURCE_WEIGHTS["unknown"])

    # Bonus for having 3+ distinct source types
    if len(sources) >= 3:
        score += 10
    elif len(sources) == 2:
        score += 5

    return min(30.0, score)


def score_signal_count(cluster: dict) -> float:
    """
    Score based on number of signals. Max 20 points.
    Single signal gets base score.
    """
    count = cluster.get("signal_count", 0)

    if count >= 10:
        return 20.0
    elif count >= 7:
        return 16.0
    elif count >= 5:
        return 12.0
    elif count >= 3:
        return 8.0
    elif count == 2:
        return 4.0
    elif count == 1:
        return 2.0
    return 0.0


def score_urgency(cluster: dict) -> float:
    """
    Score based on urgency levels of signals in cluster. Max 20 points.
    Uses highest urgency signal as primary signal.
    """
    signals = cluster.get("signals", [])
    score   = 0.0

    urgency_scores = []
    for signal in signals:
        urgency = signal.get("intent", {}).get("urgency_level", "low")
        urgency_scores.append(URGENCY_WEIGHTS.get(urgency, 0))

    if urgency_scores:
        # Weight toward the highest urgency signals
        urgency_scores.sort(reverse=True)
        score = urgency_scores[0]  # top signal
        if len(urgency_scores) > 1:
            score += urgency_scores[1] * 0.5  # second signal at half weight

    return min(20.0, score)


def score_classification_confidence(cluster: dict) -> float:
    """
    Average classification confidence across signals. Max 20 points.
    """
    signals = cluster.get("signals", [])
    if not signals:
        return 0.0

    confidences = [
        s.get("classification", {}).get("confidence", 0.0)
        for s in signals
    ]

    avg_confidence = sum(confidences) / len(confidences)
    return round(avg_confidence * 20.0, 2)


def score_recency(cluster: dict) -> float:
    """
    Score based on how recent the signals are. Max 10 points.
    Signals in last 24h = full score. Older = decaying score.
    """
    latest_str = cluster.get("latest_signal")
    if not latest_str:
        return 5.0  # neutral if unknown

    try:
        latest  = datetime.fromisoformat(latest_str)
        now     = datetime.now(timezone.utc)
        age_hrs = (now - latest).total_seconds() / 3600

        if age_hrs <= 24:
            return 10.0
        elif age_hrs <= 48:
            return 7.0
        elif age_hrs <= 72:
            return 5.0
        elif age_hrs <= 120:
            return 3.0
        else:
            return 1.0
    except ValueError:
        return 5.0


def score_weather_correlation(cluster: dict) -> float:
    """
    Bonus if cluster contains a weather signal — real-world correlation boost.
    Max 10 points.
    """
    signals = cluster.get("signals", [])
    has_weather = any(s.get("source") == "weather" for s in signals)
    return 10.0 if has_weather else 0.0


def compute_confidence_score(cluster: dict) -> int:
    """
    Compute final confidence score (0–100) from all sub-scores.

    Components:
    - Source diversity:            max 30 pts
    - Signal count:                max 20 pts
    - Urgency levels:              max 20 pts
    - Classification confidence:   max 20 pts
    - Recency:                     max 10 pts
    - Weather correlation bonus:   max 10 pts
    Total possible:                110 pts → clamped to 100
    """
    source_score     = score_source_diversity(cluster)
    count_score      = score_signal_count(cluster)
    urgency_score    = score_urgency(cluster)
    conf_score       = score_classification_confidence(cluster)
    recency_score    = score_recency(cluster)
    weather_score    = score_weather_correlation(cluster)

    total = (source_score + count_score + urgency_score +
             conf_score + recency_score + weather_score)

    final = int(min(100, max(0, round(total))))

    logger.debug(
        f"[Inference] Scoring breakdown — "
        f"source={source_score:.1f} count={count_score:.1f} "
        f"urgency={urgency_score:.1f} conf={conf_score:.1f} "
        f"recency={recency_score:.1f} weather={weather_score:.1f} "
        f"total={final}"
    )

    return final


def compute_severity(cluster: dict, confidence_score: int) -> str:
    """
    Compute severity level from confidence + urgency signals.

    critical: confidence ≥ 85 OR any signal is critical urgency
    high:     confidence ≥ 65 OR any signal is high urgency
    medium:   confidence ≥ 45
    low:      everything else
    """
    signals = cluster.get("signals", [])
    urgencies = [s.get("intent", {}).get("urgency_level", "low") for s in signals]

    if confidence_score >= 85 or "critical" in urgencies:
        return "critical"
    elif confidence_score >= 65 or "high" in urgencies:
        return "high"
    elif confidence_score >= 45:
        return "medium"
    else:
        return "low"


# ── Confidence Decay ──────────────────────────────────────────────────────────

def apply_confidence_decay(incident: dict) -> dict:
    """
    Apply time-weighted confidence decay to an existing incident.
    Called when re-evaluating an existing incident with no new signals.
    Incidents below INCIDENT_ARCHIVE_THRESHOLD get status = 'archived'.
    """
    created_at = incident.get("created_at")
    if not created_at:
        return incident

    try:
        created   = datetime.fromisoformat(created_at)
        now       = datetime.now(timezone.utc)
        age_days  = (now - created).total_seconds() / 86_400

        current_score = incident.get("confidence_score", 50)

        # Decay: lose ~5 points per day after 3 days with no new signals
        if age_days > 3:
            decay = int((age_days - 3) * 5)
            new_score = max(0, current_score - decay)
        else:
            new_score = current_score

        incident["confidence_score"] = new_score

        if new_score < INCIDENT_ARCHIVE_THRESHOLD:
            incident["status"] = "archived"
            logger.info(
                f"[Inference] Incident {incident.get('incident_id', '?')[:8]} "
                f"archived — confidence decayed to {new_score}"
            )
        elif new_score < INCIDENT_CREATION_THRESHOLD:
            incident["status"] = "monitoring"

        # Append to confidence history
        incident.setdefault("confidence_history", []).append({
            "timestamp":        now.isoformat(),
            "confidence_score": new_score,
            "reason":           "temporal_decay",
        })

    except (ValueError, TypeError) as e:
        logger.warning(f"[Inference] Decay calculation failed: {e}")

    return incident


# ── Core Agent ────────────────────────────────────────────────────────────────

def process_cluster(cluster: dict) -> Optional[dict]:
    """
    Convert a cluster into an incident if confidence > 60.

    Args:
        cluster: Cluster dict from correlation_agent.py

    Returns:
        Incident dict if confidence > threshold, None otherwise
    """
    confidence_score = compute_confidence_score(cluster)
    severity_level   = compute_severity(cluster, confidence_score)

    if confidence_score <= INCIDENT_CREATION_THRESHOLD:
        logger.info(
            f"[Inference] Cluster {cluster['cluster_id'][:8]} — "
            f"confidence {confidence_score} below threshold {INCIDENT_CREATION_THRESHOLD}, skipping"
        )
        return None

    now = datetime.now(timezone.utc).isoformat()

    incident = {
        "incident_id":       cluster["cluster_id"],   # reuse cluster ID
        "cluster_id":        cluster["cluster_id"],
        "signal_ids":        cluster["signal_ids"],
        "signal_count":      cluster["signal_count"],
        "location":          cluster["location"],
        "damage_type":       cluster["damage_type"],
        "confidence_score":  confidence_score,
        "severity_level":    severity_level,
        "status":            "active",
        "source_diversity":  cluster["source_diversity"],
        "explanation":       None,   # filled by Explanation Agent
        "created_at":        now,
        "updated_at":        now,
        "confidence_history": [
            {
                "timestamp":        now,
                "confidence_score": confidence_score,
                "reason":           "initial_scoring",
            }
        ],
    }

    logger.info(
        f"[Inference] Incident created — "
        f"id={incident['incident_id'][:8]} "
        f"confidence={confidence_score} "
        f"severity={severity_level} "
        f"damage={cluster['damage_type']} "
        f"location={cluster['location'].get('address')}"
    )

    return incident


def process_clusters(clusters: list[dict]) -> list[dict]:
    """
    Convert all clusters into incidents.
    Only returns incidents above the confidence threshold.
    """
    incidents = []

    for cluster in clusters:
        incident = process_cluster(cluster)
        if incident:
            incidents.append(incident)

    logger.info(
        f"[Inference] Done — {len(clusters)} clusters → {len(incidents)} incidents created"
    )

    return incidents


# ── Lambda Handler ────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    """
    Called by Srikar's Inference Lambda after correlation_agent.py.
    Returns incidents ready for the Explanation Agent.
    """
    clusters = event.get("clusters", [])

    if not clusters:
        return {"statusCode": 200, "incidents": [], "count": 0}

    incidents = process_clusters(clusters)

    return {
        "statusCode": 200,
        "incidents":  incidents,
        "count":      len(incidents),
    }


# ── Local Test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    test_clusters = [
        {
            # High confidence — 3 sources, critical urgency
            "cluster_id":      "cluster-001",
            "signal_ids":      ["s001", "s002", "s003"],
            "signal_count":    3,
            "damage_type":     "pothole",
            "source_diversity": ["reddit", "youtube", "times_of_india"],
            "source_count":    3,
            "latest_signal":   datetime.now(timezone.utc).isoformat(),
            "earliest_signal": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
            "location": {
                "center_coordinates": {"lat": 12.9716, "lon": 77.5946},
                "radius_meters": 500,
                "address": "Bangalore",
            },
            "signals": [
                {
                    "signal_id": "s001", "source": "social_media", "source_name": "reddit",
                    "classification": {"confidence": 0.92, "damage_type": "pothole"},
                    "intent": {"urgency_level": "high", "context_type": "direct_report"},
                },
                {
                    "signal_id": "s002", "source": "social_media", "source_name": "youtube",
                    "classification": {"confidence": 0.85, "damage_type": "pothole"},
                    "intent": {"urgency_level": "critical", "context_type": "direct_report"},
                },
                {
                    "signal_id": "s003", "source": "news", "source_name": "times_of_india",
                    "classification": {"confidence": 0.95, "damage_type": "pothole"},
                    "intent": {"urgency_level": "high", "context_type": "news_article"},
                },
            ],
        },
        {
            # Low confidence — only 2 Reddit signals, low urgency
            "cluster_id":      "cluster-002",
            "signal_ids":      ["s004", "s005"],
            "signal_count":    2,
            "damage_type":     "general",
            "source_diversity": ["reddit"],
            "source_count":    1,
            "latest_signal":   (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
            "earliest_signal": (datetime.now(timezone.utc) - timedelta(days=6)).isoformat(),
            "location": {
                "center_coordinates": {"lat": 26.9124, "lon": 75.7873},
                "radius_meters": 500,
                "address": "Jaipur",
            },
            "signals": [
                {
                    "signal_id": "s004", "source": "social_media", "source_name": "reddit",
                    "classification": {"confidence": 0.40, "damage_type": "general"},
                    "intent": {"urgency_level": "low", "context_type": "speculation"},
                },
                {
                    "signal_id": "s005", "source": "social_media", "source_name": "reddit",
                    "classification": {"confidence": 0.35, "damage_type": "general"},
                    "intent": {"urgency_level": "low", "context_type": "ambiguous"},
                },
            ],
        },
        {
            # Weather + Reddit = medium confidence
            "cluster_id":      "cluster-003",
            "signal_ids":      ["s006", "s007"],
            "signal_count":    2,
            "damage_type":     "flooding",
            "source_diversity": ["openweathermap", "reddit"],
            "source_count":    2,
            "latest_signal":   datetime.now(timezone.utc).isoformat(),
            "earliest_signal": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
            "location": {
                "center_coordinates": {"lat": 19.0760, "lon": 72.8777},
                "radius_meters": 500,
                "address": "Mumbai",
            },
            "signals": [
                {
                    "signal_id": "s006", "source": "weather", "source_name": "openweathermap",
                    "classification": {"confidence": 0.75, "damage_type": "flooding"},
                    "intent": {"urgency_level": "medium", "context_type": "weather_alert"},
                },
                {
                    "signal_id": "s007", "source": "social_media", "source_name": "reddit",
                    "classification": {"confidence": 0.82, "damage_type": "flooding"},
                    "intent": {"urgency_level": "high", "context_type": "direct_report"},
                },
            ],
        },
    ]

    print("Testing Inference Agent...\n")
    incidents = process_clusters(test_clusters)

    print(f"\nIncidents created: {len(incidents)} / {len(test_clusters)} clusters\n")
    for inc in incidents:
        print(f"Incident: {inc['incident_id'][:8]}")
        print(f"  Location:   {inc['location']['address']}")
        print(f"  Damage:     {inc['damage_type']}")
        print(f"  Confidence: {inc['confidence_score']}")
        print(f"  Severity:   {inc['severity_level']}")
        print(f"  Sources:    {inc['source_diversity']}")
        print(f"  Status:     {inc['status']}")
        print()
