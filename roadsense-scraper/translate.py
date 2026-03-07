"""
RoadSense AI — Translation Step (translate.py)
Runs on EVERY signal right after scraping, before any agent sees the text.
Auto-detects language and translates to English using AWS Translate.
Srikar handles IAM — this file just calls boto3.

Supported: Hindi, Tamil, Telugu, Kannada, Bengali, Marathi, Malayalam,
           Gujarati, and 70+ other languages (AWS Translate auto-detects).
Free tier: 2M characters/month (should be plenty for our scale, but monitor usage in AWS Console).

Fixes vs v1:
  - Weather signals (already English) are skipped to save Translate quota
  - failed_count now correctly increments on passthrough due to error
  - was_translated removed from signal output (internal field only)
"""

import boto3
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# AWS Translate client — Srikar ensures Lambda role has translate:TranslateText
translate_client = boto3.client("translate", region_name="ap-south-1")

# Languages we expect and log explicitly (informational only — auto handles all)
INDIAN_LANGUAGES = {
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
    "or": "Odia",
}


# ── Core Translation ──────────────────────────────────────────────────────────

def translate_signal(content: str) -> dict:
    """
    Translates a single piece of text to English using AWS Translate.

    Args:
        content: Raw text from scraper (any language)

    Returns:
        {
            "original_content":   <original text>,
            "translated_content": <English text>,
            "detected_language":  <ISO 639-1 code e.g. 'hi', 'ta', 'en'>,
            "was_translated":     <True if translation happened>,
            "translation_failed": <True if we fell back to passthrough due to error>
        }
    """
    if not content or not content.strip():
        return _passthrough(content, reason="empty content")

    try:
        response = translate_client.translate_text(
            Text=content,
            SourceLanguageCode="auto",   # AWS auto-detects
            TargetLanguageCode="en",
        )

        detected_lang = response["SourceLanguageCode"]
        translated    = response["TranslatedText"]
        was_translated = detected_lang != "en"

        if was_translated:
            lang_name = INDIAN_LANGUAGES.get(detected_lang, detected_lang)
            logger.info(
                f"Translated from {lang_name} ({detected_lang}): '{content[:60]}...'")

        return {
            "original_content":   content,
            "translated_content": translated,
            "detected_language":  detected_lang,
            "was_translated":     was_translated,
            "translation_failed": False,
        }

    except translate_client.exceptions.DetectedLanguageLowConfidenceException as e:
        logger.warning(f"Low language detection confidence: {e}. Passing through as-is.")
        return _passthrough(content, reason="low_confidence")

    except translate_client.exceptions.TextSizeLimitExceededException:
        # Truncate and retry — AWS Translate limit is 10,000 bytes
        logger.warning("Text too long for AWS Translate, truncating to 9000 chars")
        return translate_signal(content[:9000])

    except Exception as e:
        logger.error(f"Translation failed: {e}. Passing original content through.")
        return _passthrough(content, reason=str(e))


def _passthrough(content: str, reason: str = "") -> dict:
    """Returns signal unchanged when translation isn't possible or needed."""
    return {
        "original_content":   content,
        "translated_content": content,   # use original as fallback
        "detected_language":  "unknown",
        "was_translated":     False,
        "translation_failed": reason not in ("already_english", ""),
    }


def _passthrough_english(content: str) -> dict:
    """Fast path for signals already confirmed as English (e.g. weather)."""
    return {
        "original_content":   content,
        "translated_content": content,
        "detected_language":  "en",
        "was_translated":     False,
        "translation_failed": False,
    }


# ── Batch Processing ──────────────────────────────────────────────────────────

def translate_signals(signals: list[dict]) -> list[dict]:
    """
    Runs translation on a list of signal dicts (output from scrapers).
    Mutates each signal in place with translation fields.

    Skips signals that are already confirmed English (e.g. weather signals)
    to avoid burning AWS Translate quota unnecessarily.

    Args:
        signals: List of signal dicts from any scraper

    Returns:
        Same list with translated_content, detected_language filled in.
    """
    translated_count = 0
    skipped_count    = 0
    failed_count     = 0

    for signal in signals:
        # ── Skip: weather signals are always English ──────────────────────────
        if signal.get("detected_language") == "en" and signal.get("translated_content"):
            skipped_count += 1
            continue

        raw_content = signal.get("original_content", "")
        result = translate_signal(raw_content)

        # Write translation fields back onto the signal
        signal["original_content"]   = result["original_content"]
        signal["translated_content"] = result["translated_content"]
        signal["detected_language"]  = result["detected_language"]
        # Don't leak internal fields into the signal dict
        # was_translated / translation_failed stay out of the stored record

        if result["was_translated"]:
            translated_count += 1
        elif result["translation_failed"]:
            # Passthrough due to an actual error (not just already-English)
            failed_count += 1

    logger.info(
        f"Translation complete — {len(signals)} signals: "
        f"{translated_count} translated, "
        f"{skipped_count} skipped (already English), "
        f"{failed_count} failed (passed through)"
    )

    return signals


# ── Lambda Handler ────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    """
    Called inline by scraper_lambda before writing to DynamoDB.
    Expects event to contain a 'signals' list.
    """
    signals = event.get("signals", [])

    if not signals:
        logger.warning("No signals received for translation")
        return {"statusCode": 200, "signals": [], "count": 0}

    translated = translate_signals(signals)

    return {
        "statusCode": 200,
        "signals":    translated,
        "count":      len(translated),
    }


# ── Local Test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    test_signals = [
        {
            "signal_id": "test-001",
            "original_content": "MG Road par bahut bada gaddha hai, gaadi ka tyre phut gaya",  # Hindi
            "translated_content": None,
            "detected_language": None,
            "source": "reddit",
        },
        {
            "signal_id": "test-002",
            "original_content": "Chennai-ta road-la periya pothole irukku, car damage aaguthu",  # Tamil
            "translated_content": None,
            "detected_language": None,
            "source": "reddit",
        },
        {
            "signal_id": "test-003",
            "original_content": "Huge pothole on MG Road, damaged my car's suspension",  # English
            "translated_content": None,
            "detected_language": None,
            "source": "news",
        },
        {
            "signal_id": "test-004",
            "original_content": "Weather alert in Mumbai: moderate rain. Rainfall: 12.3mm in last hour.",
            "translated_content": "Weather alert in Mumbai: moderate rain. Rainfall: 12.3mm in last hour.",
            "detected_language": "en",   # weather signal — should be skipped
            "source": "weather",
        },
    ]

    print("Testing translate.py...\n")
    results = translate_signals(test_signals)

    for s in results:
        print(f"Signal: {s['signal_id']}")
        print(f"  Original:   {s['original_content']}")
        print(f"  Translated: {s['translated_content']}")
        print(f"  Language:   {s['detected_language']}")
        print()