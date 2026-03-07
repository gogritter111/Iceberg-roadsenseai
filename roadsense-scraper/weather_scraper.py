"""
RoadSense AI — Weather Scraper (weather_scraper.py)
Fetches real-time weather for Indian cities and generates signals
when rainfall or flooding conditions are detected.

API: OpenWeatherMap (free tier, 1000 calls/day)
Key: Provided by Sujith → stored in AWS Secrets Manager by Srikar

Fixes vs v1:
  - scrape_city() log message was saying "No alert" even when alert WAS triggered
  - RAIN_THRESHOLD_MM raised from 0.0 → 2.5mm to filter out light drizzle
"""

import os
import uuid
import hashlib
import logging
import urllib.request
import json
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ── Config ────────────────────────────────────────────────────────────────────

OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "")

BASE_URL = "https://api.openweathermap.org/data/2.5"

TARGET_CITIES = [
    {"name": "Bangalore",   "lat": 12.9716, "lon": 77.5946},
]

# Raise threshold to 2.5mm/hour — filters out light drizzle that doesn't
# pose a real road risk. Was 0.0 which caused every city with any rain to alert.
RAIN_THRESHOLD_MM = 2.5

FLOOD_WEATHER_IDS = {
    200, 201, 202,            # Thunderstorm with rain
    230, 231, 232,            # Thunderstorm with drizzle
    300, 301, 302,            # Drizzle
    500, 501, 502, 503, 504,  # Rain (light → extreme)
    511,                      # Freezing rain
    520, 521, 522, 531,       # Shower rain
    611, 612, 613,            # Sleet
    615, 616,                 # Rain and snow
    901, 902,                 # Tropical storm / hurricane
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_signal_id(city: str, timestamp: str, weather_id: int) -> str:
    hash_input   = f"weather:{city}:{timestamp}:{weather_id}".encode("utf-8")
    content_hash = hashlib.sha256(hash_input).hexdigest()
    return str(uuid.UUID(content_hash[:32]))


def fetch_json(url: str) -> dict:
    """Simple HTTP GET — no external libraries needed."""
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        raise RuntimeError(f"HTTP request failed: {e}")


def build_description(city: str, weather: dict) -> str:
    """Build a human-readable signal description from weather data."""
    condition  = weather["description"]
    temp       = weather["temp"]
    humidity   = weather["humidity"]
    rain_1h    = weather.get("rain_1h", 0)
    wind_speed = weather.get("wind_speed", 0)

    parts = [f"Weather alert in {city}: {condition.capitalize()}."]

    if rain_1h > 0:
        parts.append(f"Rainfall: {rain_1h:.1f}mm in last hour.")
    if humidity > 85:
        parts.append(f"High humidity: {humidity}%.")
    if wind_speed > 10:
        parts.append(f"Wind speed: {wind_speed} m/s.")

    parts.append(f"Temperature: {temp}°C.")
    parts.append("Potential road flooding or waterlogging risk.")

    return " ".join(parts)


def should_generate_signal(weather: dict) -> tuple[bool, str]:
    """
    Decide if weather conditions warrant a road risk signal.
    Returns (should_signal, reason).
    """
    weather_id  = weather["weather_id"]
    rain_1h     = weather.get("rain_1h", 0)
    description = weather["description"].lower()

    if rain_1h >= RAIN_THRESHOLD_MM:
        return True, f"Significant rainfall: {rain_1h}mm/hour"

    if weather_id in FLOOD_WEATHER_IDS:
        return True, f"Rain condition detected: {description}"

    if "flood" in description or "waterlog" in description:
        return True, f"Flood condition: {description}"

    if "heavy" in description and "rain" in description:
        return True, f"Heavy rain: {description}"

    return False, ""


# ── Core Scraper ──────────────────────────────────────────────────────────────

def fetch_weather(city: dict) -> dict | None:
    """
    Fetch current weather for a city using OpenWeatherMap.
    Returns normalised weather dict or None on failure.
    """
    url = (
        f"{BASE_URL}/weather"
        f"?lat={city['lat']}&lon={city['lon']}"
        f"&appid={OPENWEATHER_API_KEY}"
        f"&units=metric"
    )

    try:
        data    = fetch_json(url)
        rain_1h = data.get("rain", {}).get("1h", 0.0)

        return {
            "city":        city["name"],
            "lat":         city["lat"],
            "lon":         city["lon"],
            "weather_id":  data["weather"][0]["id"],
            "description": data["weather"][0]["description"],
            "temp":        data["main"]["temp"],
            "humidity":    data["main"]["humidity"],
            "wind_speed":  data["wind"]["speed"],
            "rain_1h":     rain_1h,
            "timestamp":   datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"[Weather] Failed to fetch weather for {city['name']}: {e}")
        return None


def scrape_city(city: dict) -> list[dict]:
    """Fetch weather for one city and return signals if conditions warrant it."""
    weather = fetch_weather(city)
    if not weather:
        return []

    should_signal, reason = should_generate_signal(weather)

    if not should_signal:
        # Fixed: this branch correctly says "No alert"
        logger.info(
            f"[Weather] {city['name']}: No alert — "
            f"{weather['description']}, rain: {weather['rain_1h']}mm"
        )
        return []

    # Fixed: this branch now correctly says "Alert triggered"
    logger.info(
        f"[Weather] {city['name']}: Alert triggered — "
        f"{reason}, condition: {weather['description']}, "
        f"rain: {weather['rain_1h']}mm"
    )

    description = build_description(city["name"], weather)

    signal = {
        "signal_id":          make_signal_id(city["name"], weather["timestamp"], weather["weather_id"]),
        "source":             "weather",
        "source_name":        "openweathermap",
        "original_content":   description,
        "translated_content": description,   # already English — translate.py will skip
        "detected_language":  "en",
        "city":               city["name"],
        "timestamp":          weather["timestamp"],
        "location": {
            "coordinates": {
                "lat": city["lat"],
                "lon": city["lon"],
            },
            "accuracy_meters": 1000,
            "address":         city["name"],
        },
        "weather_data": {
            "condition":   weather["description"],
            "weather_id":  weather["weather_id"],
            "rain_1h_mm":  weather["rain_1h"],
            "humidity":    weather["humidity"],
            "wind_speed":  weather["wind_speed"],
            "temp_c":      weather["temp"],
        },
        "classification": None,   # filled by Classification Agent
        "intent":         None,   # filled by Intent & Context Agent
    }

    return [signal]


def scrape_all_cities() -> list[dict]:
    global OPENWEATHER_API_KEY
    OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")

    if not OPENWEATHER_API_KEY:
        logger.error("[Weather] OPENWEATHER_API_KEY not set — cannot run scraper")
        return []

    all_signals = []
    for city in TARGET_CITIES:
        signals = scrape_city(city)
        all_signals.extend(signals)

    logger.info(f"[Weather] Done — {len(all_signals)} weather signals generated")
    return all_signals


# ── Lambda Handler ────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    """
    Entry point for Srikar's Scraper Lambda.
    Weather signals are already in English — translate.py will skip them.
    """
    signals = scrape_all_cities()
    return {
        "statusCode": 200,
        "signals":    signals,
        "count":      len(signals),
    }


# ── Local Test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Running weather scraper locally...\n")
    results = scrape_all_cities()

    print(f"\nTotal weather signals: {len(results)}")
    if results:
        print("\nSample signal:")
        print(json.dumps(results[0], indent=2, default=str))
    else:
        print("No alert conditions detected in any city right now — that's normal!")
        print("Try again during monsoon season or a rainy day :)")