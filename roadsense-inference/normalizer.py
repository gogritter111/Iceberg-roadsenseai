"""
RoadSense AI — Location Normaliser (location_normaliser.py)
Handles mismatched location structures across different signal sources.

Dataset format:    {"latitude": 12.97, "longitude": 77.60, "accuracy_meters": 56, "address": "MG Road"}
Pipeline format:   {"coordinates": {"lat": 12.97, "lon": 77.60}, "accuracy_meters": 56, "address": "MG Road"}

Call this once at ingestion — before any agent sees the signal.
"""

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def normalise_location(location: dict) -> dict:
    """
    Normalise a location dict to pipeline format.
    Handles both dataset format and pipeline format gracefully.

    Args:
        location: Raw location dict from any source

    Returns:
        Normalised location dict in pipeline format
    """
    if not location:
        return {
            "coordinates":    None,
            "accuracy_meters": None,
            "address":        None,
        }

    # Already in pipeline format — has nested coordinates
    if "coordinates" in location:
        return location

    # Dataset format — flat latitude/longitude
    lat = location.get("latitude") or location.get("lat")
    lon = location.get("longitude") or location.get("lon") or location.get("lng")

    coordinates = {"lat": float(lat), "lon": float(lon)} if lat and lon else None

    return {
        "coordinates":    coordinates,
        "accuracy_meters": location.get("accuracy_meters"),
        "address":        location.get("address"),
    }


def normalise_signal(signal: dict) -> dict:
    """Normalise location field in a single signal dict."""
    if "location" in signal:
        signal["location"] = normalise_location(signal["location"])
    return signal


def normalise_signals(signals: list[dict]) -> list[dict]:
    """Normalise location fields across all signals."""
    for signal in signals:
        normalise_signal(signal)
    logger.info(f"[LocationNormaliser] Normalised {len(signals)} signals")
    return signals


# ── Local Test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    test_cases = [
        # Dataset format
        {
            "signal_id": "s001",
            "location": {
                "latitude": 12.975106,
                "longitude": 77.606075,
                "accuracy_meters": 56,
                "address": "MG Road"
            }
        },
        # Pipeline format — should pass through unchanged
        {
            "signal_id": "s002",
            "location": {
                "coordinates": {"lat": 19.0760, "lon": 72.8777},
                "accuracy_meters": 1000,
                "address": "Mumbai"
            }
        },
        # Missing location entirely
        {
            "signal_id": "s003",
            "location": None
        },
        # Partial location — only address
        {
            "signal_id": "s004",
            "location": {"address": "Hyderabad"}
        },
    ]

    print("Testing Location Normaliser...\n")
    results = normalise_signals(test_cases)
    for s in results:
        print(f"Signal {s['signal_id']}:")
        print(f"  {json.dumps(s['location'], indent=4)}")
        print()

    # Test against actual dataset
    print("Testing against signals.json...")
    try:
        with open("/mnt/user-data/uploads/signals.json") as f:
            signals = json.load(f)

        normalised = normalise_signals(signals)

        # Verify all locations are now in pipeline format
        broken = [
            s for s in normalised
            if s.get("location") and "latitude" in s.get("location", {})
        ]
        print(f"Total signals:        {len(normalised)}")
        print(f"Still in old format:  {len(broken)} (should be 0)")

        coords_present = [
            s for s in normalised
            if s.get("location", {}).get("coordinates")
        ]
        print(f"With coordinates:     {len(coords_present)}")
        print()
        print("Sample normalised location:")
        print(json.dumps(normalised[0]["location"], indent=2))
    except FileNotFoundError:
        print("signals.json not found — run this from the project root")
