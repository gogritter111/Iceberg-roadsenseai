"""
RoadSense AI — Correlation Agent (correlation_agent.py)
Clusters signals by geographic location and time window using semantic embeddings.

Model: Titan Embeddings V2 (via bedrock_client.py from Srikar)
Input: signals with classification + intent fields populated
Output: list of clusters, each representing a potential incident

Clustering rules:
- Geographic radius: 500m
- Time window: 7-day sliding window
- Minimum signals to form a cluster: 2
"""

import math
import hashlib
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from bedrock_client import get_embedding

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ── Config ────────────────────────────────────────────────────────────────────

GEO_RADIUS_METERS   = 500     # signals within 500m are considered co-located
TIME_WINDOW_DAYS    = 7       # 7-day sliding window
MIN_CLUSTER_SIZE    = 1       # minimum signals to form an incident cluster
SIMILARITY_THRESHOLD = 0.75   # cosine similarity threshold for semantic clustering


# ── Geo Utilities ─────────────────────────────────────────────────────────────

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance in meters between two lat/lon points.
    Uses Haversine formula.
    """
    R = 6_371_000  # Earth radius in meters

    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    d_phi = math.radians(float(lat2) - float(lat1))
    d_lam = math.radians(float(lon2) - float(lon1))

    a = (math.sin(d_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def within_radius(s1: dict, s2: dict, radius_meters: float = GEO_RADIUS_METERS) -> bool:
    """Returns True if two signals are within the geo radius."""
    c1 = s1.get("location", {}).get("coordinates")
    c2 = s2.get("location", {}).get("coordinates")

    if not c1 or not c2:
        # If no coordinates, fall back to city-level matching
        city1 = s1.get("city", "").lower()
        city2 = s2.get("city", "").lower()
        return bool(city1 and city2 and city1 == city2)

    return haversine_distance(c1["lat"], c1["lon"], c2["lat"], c2["lon"]) <= radius_meters


def within_time_window(s1: dict, s2: dict, days: int = TIME_WINDOW_DAYS) -> bool:
    """Returns True if two signals are within the time window."""
    try:
        t1 = datetime.fromisoformat(s1["timestamp"])
        t2 = datetime.fromisoformat(s2["timestamp"])
        return abs((t1 - t2).total_seconds()) <= days * 86_400
    except (KeyError, ValueError):
        return True  # assume within window if timestamp missing


def compute_cluster_center(signals: list[dict]) -> dict:
    """Compute the geographic centroid of a cluster."""
    import json
    
    coords = []
    for s in signals:
        location = s.get("location", {})
        if isinstance(location, str):
            try:
                location = json.loads(location)
            except:
                location = {}
        
        coordinates = location.get("coordinates")
        if coordinates:
            # Ensure lat/lon are floats
            try:
                lat = float(coordinates["lat"])
                lon = float(coordinates["lon"])
                coords.append({"lat": lat, "lon": lon})
            except (KeyError, ValueError, TypeError):
                pass

    if not coords:
        # Fall back to address from location
        location = signals[0].get("location", {}) if signals else {}
        if isinstance(location, str):
            try:
                location = json.loads(location)
            except:
                location = {}
        address = location.get("address")
        return {"lat": None, "lon": None, "address": address}

    avg_lat = sum(c["lat"] for c in coords) / len(coords)
    avg_lon = sum(c["lon"] for c in coords) / len(coords)
    
    # Get address from first signal's location
    location = signals[0].get("location", {})
    if isinstance(location, str):
        try:
            location = json.loads(location)
        except:
            location = {}
    address = location.get("address")

    return {"lat": avg_lat, "lon": avg_lon, "address": address}


# ── Embedding Utilities ───────────────────────────────────────────────────────

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot     = sum(a * b for a, b in zip(v1, v2))
    norm1   = math.sqrt(sum(a * a for a in v1))
    norm2   = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def get_signal_embedding(signal: dict) -> Optional[list[float]]:
    """Fetch Titan embedding for a signal's translated content."""
    text = signal.get("translated_content") or signal.get("original_content", "")
    if not text.strip():
        return None
    try:
        return get_embedding(text)
    except Exception as e:
        logger.warning(f"[Correlation] Embedding failed for signal {signal.get('signal_id', '?')[:8]}: {e}")
        return None


def semantically_similar(emb1: Optional[list], emb2: Optional[list]) -> bool:
    """Returns True if two embeddings are above similarity threshold."""
    if emb1 is None or emb2 is None:
        return True  # can't check — assume similar to avoid false negatives
    return cosine_similarity(emb1, emb2) >= SIMILARITY_THRESHOLD


# ── Cluster ID ────────────────────────────────────────────────────────────────

def make_cluster_id(signal_ids: list[str]) -> str:
    """Deterministic cluster ID from sorted signal IDs."""
    combined = ":".join(sorted(signal_ids))
    h = hashlib.sha256(combined.encode()).hexdigest()
    return str(uuid.UUID(h[:32]))


# ── Core Clustering ───────────────────────────────────────────────────────────

def filter_eligible_signals(signals: list[dict]) -> list[dict]:
    """
    Only pass signals that are:
    - Road related
    - Problem reports (or weather alerts)
    - Not already discarded
    """
    eligible = []
    for s in signals:
        classification = s.get("classification", {})
        intent         = s.get("intent", {})

        is_road    = classification.get("is_road_related", False)
        is_problem = intent.get("is_problem_report", False)
        is_weather = s.get("source") == "weather"

        if is_road and (is_problem or is_weather):
            eligible.append(s)

    logger.info(f"[Correlation] {len(eligible)} / {len(signals)} signals eligible for clustering")
    return eligible


def cluster_signals(signals: list[dict]) -> list[dict]:
    """
    Main clustering function.
    Groups signals into clusters based on:
    1. Geographic proximity (500m radius or same city)
    2. Time window (7-day sliding window)
    3. Semantic similarity (Titan Embeddings V2)

    Returns list of cluster dicts.
    """
    eligible = filter_eligible_signals(signals)

    if not eligible:
        logger.info("[Correlation] No eligible signals to cluster")
        return []

    # Fetch embeddings for all eligible signals
    logger.info(f"[Correlation] Fetching embeddings for {len(eligible)} signals...")
    embeddings = {}
    for signal in eligible:
        emb = get_signal_embedding(signal)
        if emb:
            embeddings[signal["signal_id"]] = emb

    # Union-Find clustering
    parent = {s["signal_id"]: s["signal_id"] for s in eligible}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        parent[find(x)] = find(y)

    # Compare every pair of signals
    for i in range(len(eligible)):
        for j in range(i + 1, len(eligible)):
            s1 = eligible[i]
            s2 = eligible[j]

            if not within_time_window(s1, s2):
                continue
            if not within_radius(s1, s2):
                continue

            emb1 = embeddings.get(s1["signal_id"])
            emb2 = embeddings.get(s2["signal_id"])
            if not semantically_similar(emb1, emb2):
                continue

            union(s1["signal_id"], s2["signal_id"])

    # Group signals by cluster root
    cluster_map: dict[str, list[dict]] = {}
    for signal in eligible:
        root = find(signal["signal_id"])
        cluster_map.setdefault(root, []).append(signal)

    # Build cluster objects — only keep clusters with enough signals
    clusters = []
    for root, cluster_signals_list in cluster_map.items():
        if len(cluster_signals_list) < MIN_CLUSTER_SIZE:
            logger.info(
                f"[Correlation] Cluster {root[:8]} discarded — "
                f"only {len(cluster_signals_list)} signal(s), need {MIN_CLUSTER_SIZE}"
            )
            continue

        signal_ids   = [s["signal_id"] for s in cluster_signals_list]
        cluster_id   = make_cluster_id(signal_ids)
        center       = compute_cluster_center(cluster_signals_list)
        damage_types = [
            s["classification"].get("damage_type")
            for s in cluster_signals_list
            if s["classification"].get("damage_type")
        ]
        # Pick most common damage type
        primary_damage = max(set(damage_types), key=damage_types.count) if damage_types else "general"

        # Source diversity — important for Inference Agent confidence boosting
        sources = list({s.get("source_name", s.get("source", "unknown")) for s in cluster_signals_list})

        timestamps = []
        for s in cluster_signals_list:
            try:
                timestamps.append(datetime.fromisoformat(s["timestamp"]))
            except (KeyError, ValueError):
                pass

        cluster = {
            "cluster_id":      cluster_id,
            "signal_ids":      signal_ids,
            "signal_count":    len(cluster_signals_list),
            "signals":         cluster_signals_list,
            "location": {
                "center_coordinates": {
                    "lat": center["lat"],
                    "lon": center["lon"],
                },
                "radius_meters": GEO_RADIUS_METERS,
                "address":       center["address"],
            },
            "damage_type":     primary_damage,
            "source_diversity": sources,
            "source_count":    len(sources),
            "earliest_signal": min(timestamps).isoformat() if timestamps else None,
            "latest_signal":   max(timestamps).isoformat() if timestamps else None,
            "created_at":      datetime.now(timezone.utc).isoformat(),
        }

        clusters.append(cluster)
        logger.info(
            f"[Correlation] Cluster {cluster_id[:8]} — "
            f"{len(cluster_signals_list)} signals, "
            f"sources: {sources}, "
            f"damage: {primary_damage}, "
            f"location: {center['address']}"
        )

    logger.info(f"[Correlation] Done — {len(clusters)} clusters formed from {len(eligible)} signals")
    return clusters


# ── Lambda Handler ────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    """
    Called by Srikar's Inference Lambda after intent_agent.py.
    Returns clusters ready for the Inference Agent.
    """
    signals = event.get("signals", [])

    if not signals:
        return {"statusCode": 200, "clusters": [], "count": 0}

    clusters = cluster_signals(signals)

    return {
        "statusCode": 200,
        "clusters":   clusters,
        "count":      len(clusters),
    }


# ── Local Test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import json
    from unittest.mock import MagicMock, patch

    # Mock embeddings — return similar vectors for road signals
    def mock_embedding(text: str) -> list[float]:
        base = [0.1] * 256
        if "pothole" in text.lower() or "road" in text.lower():
            base[0] = 0.9
            base[1] = 0.8
        if "flood" in text.lower() or "waterlog" in text.lower():
            base[0] = 0.7
            base[2] = 0.9
        return base

    mock_bedrock = MagicMock()
    mock_bedrock.get_embedding.side_effect = mock_embedding
    sys.modules["bedrock_client"] = mock_bedrock

    with patch("__main__.get_embedding", mock_bedrock.get_embedding):

        test_signals = [
            # Cluster 1 — 3 pothole signals in Bangalore, MG Road area
            {
                "signal_id": "s001", "source": "social_media", "source_name": "reddit",
                "translated_content": "Huge pothole on MG Road near Trinity Circle",
                "city": "Bangalore",
                "timestamp": "2026-02-25T10:00:00+00:00",
                "location": {"coordinates": {"lat": 12.9716, "lon": 77.5946}},
                "classification": {"is_road_related": True, "damage_type": "pothole", "confidence": 0.92},
                "intent": {"is_problem_report": True, "urgency_level": "high", "context_type": "direct_report", "confidence_modifier": 0.1},
            },
            {
                "signal_id": "s002", "source": "social_media", "source_name": "youtube",
                "translated_content": "Road full of potholes near MG Road Bangalore",
                "city": "Bangalore",
                "timestamp": "2026-02-26T08:00:00+00:00",
                "location": {"coordinates": {"lat": 12.9720, "lon": 77.5950}},
                "classification": {"is_road_related": True, "damage_type": "pothole", "confidence": 0.88},
                "intent": {"is_problem_report": True, "urgency_level": "medium", "context_type": "direct_report", "confidence_modifier": 0.1},
            },
            {
                "signal_id": "s003", "source": "news", "source_name": "times_of_india",
                "translated_content": "Potholes on MG Road causing traffic chaos in Bangalore",
                "city": "Bangalore",
                "timestamp": "2026-02-27T06:00:00+00:00",
                "location": {"coordinates": {"lat": 12.9718, "lon": 77.5948}},
                "classification": {"is_road_related": True, "damage_type": "pothole", "confidence": 0.95},
                "intent": {"is_problem_report": True, "urgency_level": "high", "context_type": "news_article", "confidence_modifier": 0.15},
            },
            # Cluster 2 — flooding in Mumbai, different location
            {
                "signal_id": "s004", "source": "weather", "source_name": "openweathermap",
                "translated_content": "Weather alert in Mumbai: Heavy rainfall. Flooding risk.",
                "city": "Mumbai",
                "timestamp": "2026-02-27T09:00:00+00:00",
                "location": {"coordinates": {"lat": 19.0760, "lon": 72.8777}},
                "classification": {"is_road_related": True, "damage_type": "flooding", "confidence": 0.75},
                "intent": {"is_problem_report": True, "urgency_level": "medium", "context_type": "weather_alert", "confidence_modifier": 0.0},
            },
            {
                "signal_id": "s005", "source": "social_media", "source_name": "reddit",
                "translated_content": "Road completely flooded near Dadar, Mumbai",
                "city": "Mumbai",
                "timestamp": "2026-02-27T10:00:00+00:00",
                "location": {"coordinates": {"lat": 19.0178, "lon": 72.8478}},
                "classification": {"is_road_related": True, "damage_type": "flooding", "confidence": 0.89},
                "intent": {"is_problem_report": True, "urgency_level": "critical", "context_type": "direct_report", "confidence_modifier": 0.2},
            },
            # Lone signal — should NOT form a cluster
            {
                "signal_id": "s006", "source": "social_media", "source_name": "reddit",
                "translated_content": "Some road issue in Jaipur maybe",
                "city": "Jaipur",
                "timestamp": "2026-02-27T11:00:00+00:00",
                "location": {"coordinates": {"lat": 26.9124, "lon": 75.7873}},
                "classification": {"is_road_related": True, "damage_type": "general", "confidence": 0.35},
                "intent": {"is_problem_report": False, "urgency_level": "low", "context_type": "speculation", "confidence_modifier": -0.2},
            },
        ]

        print("Testing Correlation Agent...\n")
        clusters = cluster_signals(test_signals)

        print(f"\nClusters formed: {len(clusters)}\n")
        for c in clusters:
            print(f"Cluster: {c['cluster_id'][:8]}")
            print(f"  Signals:    {c['signal_count']}")
            print(f"  Location:   {c['location']['address']}")
            print(f"  Damage:     {c['damage_type']}")
            print(f"  Sources:    {c['source_diversity']}")
            print(f"  Time range: {c['earliest_signal']} → {c['latest_signal']}")
            print()
