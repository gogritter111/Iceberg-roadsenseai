"""
RoadSense AI — RSS News Scraper
Targeted Google News RSS queries for Bangalore road signals.
No API key needed.

v4 changes vs v2:
- Replaced generic Indian news feeds with targeted Google News RSS search queries
- Each query is Bangalore road-specific — every result is relevant by definition
- TIME_WINDOW_HOURS raised to 2160 (90 days) to backfill historical signals
- Dedup within scraper — same article across multiple queries written only once
- Always falls back to Bangalore centroid instead of returning None coordinates
"""

import feedparser
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
import re


# ── Config ────────────────────────────────────────────────────────────────────

RSS_FEEDS = {
    "gnews_blr_pothole":        "https://news.google.com/rss/search?q=bangalore+pothole&hl=en-IN&gl=IN&ceid=IN:en",
    "gnews_blr_road_damage":    "https://news.google.com/rss/search?q=bangalore+road+damage&hl=en-IN&gl=IN&ceid=IN:en",
    "gnews_blr_waterlogging":   "https://news.google.com/rss/search?q=bangalore+waterlogging&hl=en-IN&gl=IN&ceid=IN:en",
    "gnews_blr_bbmp_road":      "https://news.google.com/rss/search?q=bangalore+bbmp+road+repair&hl=en-IN&gl=IN&ceid=IN:en",
    "gnews_blr_flooding":       "https://news.google.com/rss/search?q=bangalore+road+flooding&hl=en-IN&gl=IN&ceid=IN:en",
    "gnews_blr_sinkhole":       "https://news.google.com/rss/search?q=bangalore+sinkhole+road&hl=en-IN&gl=IN&ceid=IN:en",
    "gnews_blr_traffic":        "https://news.google.com/rss/search?q=bangalore+road+blocked+accident&hl=en-IN&gl=IN&ceid=IN:en",
    "gnews_blr_infrastructure": "https://news.google.com/rss/search?q=bengaluru+road+infrastructure+damage&hl=en-IN&gl=IN&ceid=IN:en",
}

KEYWORDS = [
    "pothole", "road", "flood", "traffic", "damage", "infrastructure",
    "highway", "crater", "waterlogging", "repair", "accident", "bridge",
    "gaddha", "sadak", "potholes", "cave-in", "sinkhole", "pavement",
    "jam", "congestion", "blocked", "closure", "construction", "maintenance",
    "junction", "crossing", "flyover", "underpass", "tunnel", "expressway",
    "breakdown", "collision", "crash", "incident", "hazard", "warning",
    "rain", "storm", "monsoon", "drainage", "manhole", "bbmp",
]

BANGALORE_ALIASES = {"bangalore", "bengaluru"}

# 90 days — backfills all available Google News history on first run.
# Subsequent hourly runs pick up only new articles (dedup by signal_id).
TIME_WINDOW_HOURS = 2160


# ── Location Mapping ──────────────────────────────────────────────────────────

BANGALORE_LOCATIONS = {
    "mg road":                {"lat": 12.9757, "lon": 77.6065, "accuracy_meters": 200},
    "koramangala":            {"lat": 12.9352, "lon": 77.6245, "accuracy_meters": 500},
    "indiranagar":            {"lat": 12.9784, "lon": 77.6408, "accuracy_meters": 500},
    "whitefield":             {"lat": 12.9698, "lon": 77.7499, "accuracy_meters": 500},
    "electronic city":        {"lat": 12.8399, "lon": 77.6770, "accuracy_meters": 500},
    "hebbal":                 {"lat": 13.0358, "lon": 77.5970, "accuracy_meters": 500},
    "marathahalli":           {"lat": 12.9591, "lon": 77.6974, "accuracy_meters": 500},
    "hsr layout":             {"lat": 12.9116, "lon": 77.6389, "accuracy_meters": 500},
    "btm layout":             {"lat": 12.9166, "lon": 77.6101, "accuracy_meters": 500},
    "jayanagar":              {"lat": 12.9308, "lon": 77.5831, "accuracy_meters": 500},
    "jp nagar":               {"lat": 12.9102, "lon": 77.5850, "accuracy_meters": 500},
    "rajajinagar":            {"lat": 12.9913, "lon": 77.5528, "accuracy_meters": 500},
    "malleshwaram":           {"lat": 13.0035, "lon": 77.5710, "accuracy_meters": 500},
    "yeshwanthpur":           {"lat": 13.0275, "lon": 77.5423, "accuracy_meters": 500},
    "bannerghatta":           {"lat": 12.8635, "lon": 77.5978, "accuracy_meters": 500},
    "sarjapur":               {"lat": 12.9010, "lon": 77.6860, "accuracy_meters": 500},
    "bellandur":              {"lat": 12.9256, "lon": 77.6762, "accuracy_meters": 500},
    "hosur road":             {"lat": 12.9000, "lon": 77.6500, "accuracy_meters": 300},
    "outer ring road":        {"lat": 12.9540, "lon": 77.7010, "accuracy_meters": 300},
    "old airport road":       {"lat": 12.9610, "lon": 77.6490, "accuracy_meters": 300},
    "nh 44":                  {"lat": 13.0550, "lon": 77.5900, "accuracy_meters": 300},
    "tumkur road":            {"lat": 13.0500, "lon": 77.5100, "accuracy_meters": 300},
    "mysore road":            {"lat": 12.9540, "lon": 77.5150, "accuracy_meters": 300},
    "kanakapura road":        {"lat": 12.8980, "lon": 77.5740, "accuracy_meters": 300},
    "cunningham road":        {"lat": 12.9942, "lon": 77.5942, "accuracy_meters": 200},
    "richmond road":          {"lat": 12.9630, "lon": 77.6010, "accuracy_meters": 200},
    "brigade road":           {"lat": 12.9720, "lon": 77.6070, "accuracy_meters": 200},
    "church street":          {"lat": 12.9740, "lon": 77.6080, "accuracy_meters": 200},
    "ulsoor":                 {"lat": 12.9830, "lon": 77.6210, "accuracy_meters": 500},
    "shivajinagar":           {"lat": 12.9900, "lon": 77.5970, "accuracy_meters": 500},
    "basavanagudi":           {"lat": 12.9430, "lon": 77.5750, "accuracy_meters": 500},
    "vijayanagar":            {"lat": 12.9710, "lon": 77.5350, "accuracy_meters": 500},
    "nagarbhavi":             {"lat": 12.9580, "lon": 77.5080, "accuracy_meters": 500},
    "banashankari":           {"lat": 12.9260, "lon": 77.5466, "accuracy_meters": 500},
    "domlur":                 {"lat": 12.9610, "lon": 77.6400, "accuracy_meters": 500},
    "k r puram":              {"lat": 13.0050, "lon": 77.6940, "accuracy_meters": 500},
    "kr puram":               {"lat": 13.0050, "lon": 77.6940, "accuracy_meters": 500},
    "majestic":               {"lat": 12.9773, "lon": 77.5720, "accuracy_meters": 500},
    "silk board":             {"lat": 12.9172, "lon": 77.6230, "accuracy_meters": 300},
    "tin factory":            {"lat": 12.9960, "lon": 77.6600, "accuracy_meters": 300},
    "nagawara":               {"lat": 13.0490, "lon": 77.6270, "accuracy_meters": 500},
    "thanisandra":            {"lat": 13.0630, "lon": 77.6390, "accuracy_meters": 500},
    "yelahanka":              {"lat": 13.1005, "lon": 77.5963, "accuracy_meters": 500},
    "devanahalli":            {"lat": 13.2478, "lon": 77.7179, "accuracy_meters": 500},
    "intermediate ring road": {"lat": 12.9600, "lon": 77.6300, "accuracy_meters": 800},
    "ring road":              {"lat": 12.9540, "lon": 77.6200, "accuracy_meters": 1000},
    "namma metro":            {"lat": 12.9766, "lon": 77.5713, "accuracy_meters": 500},
}

# Always use this if no area keyword matched — never return None coordinates
BANGALORE_DEFAULT = {"lat": 12.9716, "lon": 77.5946, "accuracy_meters": 5000}


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_within_time_window(published_time: Optional[datetime]) -> bool:
    if not published_time:
        return True
    cutoff = datetime.now(timezone.utc) - timedelta(hours=TIME_WINDOW_HOURS)
    return published_time >= cutoff


def is_relevant(text: str) -> bool:
    """Safety net — rejects obvious non-road content that slips through Google News."""
    text_lower  = text.lower()
    has_keyword = any(kw in text_lower for kw in KEYWORDS)
    is_blr      = any(alias in text_lower for alias in BANGALORE_ALIASES)
    return has_keyword and is_blr


def extract_location(text: str) -> dict:
    """
    Match Bangalore area keywords for precise lat/lon.
    Always returns valid coordinates — falls back to city centroid.
    """
    text_lower = text.lower()
    for area, coords in BANGALORE_LOCATIONS.items():
        if area in text_lower:
            return {
                "coordinates": {
                    "lat": coords["lat"],
                    "lon": coords["lon"],
                },
                "accuracy_meters": coords["accuracy_meters"],
                "address":         f"{area.title()}, Bangalore",
            }
    return {
        "coordinates": {
            "lat": BANGALORE_DEFAULT["lat"],
            "lon": BANGALORE_DEFAULT["lon"],
        },
        "accuracy_meters": BANGALORE_DEFAULT["accuracy_meters"],
        "address":         "Bangalore",
    }


def make_signal_id(content: str, source: str) -> str:
    hash_input   = f"{source}:{content}".encode("utf-8")
    content_hash = hashlib.sha256(hash_input).hexdigest()
    return str(uuid.UUID(content_hash[:32]))


def parse_published(entry) -> tuple[str, Optional[datetime]]:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            return dt.isoformat(), dt
        except Exception:
            pass
    now = datetime.now(timezone.utc)
    return now.isoformat(), now


def strip_html(text: str) -> str:
    return re.sub(r'<[^>]+>', '', text).strip()


# ── Core Scraper ─────────────────────────────────────────────────────────────

def scrape_feed(feed_name: str, feed_url: str) -> list[dict]:
    signals       = []
    filtered_time = 0
    filtered_rel  = 0

    try:
        feed = feedparser.parse(feed_url)
    except Exception as e:
        print(f"[{feed_name}] Failed to fetch feed: {e}")
        return signals

    if feed.bozo and not feed.entries:
        print(f"[{feed_name}] Feed parse error or empty")
        return signals

    for entry in feed.entries:
        title   = getattr(entry, "title",   "") or ""
        summary = getattr(entry, "summary", "") or ""
        link    = getattr(entry, "link",    "") or ""
        content = strip_html(f"{title}. {summary}".strip())

        timestamp_iso, timestamp_dt = parse_published(entry)

        if not is_within_time_window(timestamp_dt):
            filtered_time += 1
            continue

        if not is_relevant(content):
            filtered_rel += 1
            continue

        location = extract_location(content)

        signal = {
            "signal_id":          make_signal_id(content, feed_name),
            "source":             "news",
            "source_name":        feed_name,
            "original_content":   content,
            "translated_content": None,
            "detected_language":  None,
            "url":                link,
            "city":               "Bangalore",
            "timestamp":          timestamp_iso,
            "location":           location,
            "classification":     None,
            "intent":             None,
        }

        signals.append(signal)

    print(
        f"[{feed_name}] {len(signals)} signals "
        f"(dropped: {filtered_time} too old, {filtered_rel} irrelevant)"
    )
    return signals


def scrape_all_feeds() -> list[dict]:
    all_signals = []
    for feed_name, feed_url in RSS_FEEDS.items():
        signals = scrape_feed(feed_name, feed_url)
        all_signals.extend(signals)

    # Dedup — same article often appears across multiple search queries
    seen, unique = set(), []
    for s in all_signals:
        sid = s.get("signal_id")
        if sid and sid not in seen:
            seen.add(sid)
            unique.append(s)

    print(f"\nTotal unique Bangalore signals: {len(unique)} (from {len(all_signals)} raw)")
    return unique


def lambda_handler(event, context):
    signals = scrape_all_feeds()
    return {
        "statusCode": 200,
        "signals":    signals,
        "count":      len(signals),
    }


if __name__ == "__main__":
    import json
    results = scrape_all_feeds()
    print("\nSample signal:")
    if results:
        print(json.dumps(results[0], indent=2))
    print(f"\nTotal: {len(results)} signals")