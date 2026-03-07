"""
RoadSense AI — Bedrock Client (bedrock_client.py)
Wraps Amazon Nova Micro, Nova Lite, and Titan Embeddings V2.

Models used:
  - amazon.nova-micro-v1:0   → classify()      fast classification (replaces Claude Haiku)
  - amazon.nova-lite-v1:0    → generate()      explanation prose  (replaces Claude Sonnet)
  - amazon.titan-embed-text-v2:0 → get_embedding() semantic clustering

All three are available in us-east-1 without manual access approval.
"""

import json
import os
import logging

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ── Config ────────────────────────────────────────────────────────────────────
BEDROCK_REGION  = os.environ.get("BEDROCK_REGION", "us-east-1")

CLASSIFY_MODEL  = "amazon.nova-micro-v1:0"   # fast, cheap — used for classification + intent
GENERATE_MODEL  = "amazon.nova-lite-v1:0"    # better prose — used for explanation
EMBED_MODEL     = "amazon.titan-embed-text-v2:0"
# ─────────────────────────────────────────────────────────────────────────────

bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)


# ── Core Invoker ──────────────────────────────────────────────────────────────

def _invoke_nova(model_id: str, prompt: str, max_tokens: int = 1024) -> str:
    """
    Invoke an Amazon Nova model via the Converse API.
    Returns the text response as a plain string.
    """
    response = bedrock.converse(
        modelId=model_id,
        messages=[
            {
                "role": "user",
                "content": [{"text": prompt}]
            }
        ],
        inferenceConfig={
            "maxTokens": max_tokens,
            "temperature": 0.1,   # low temp — we want consistent structured output
        }
    )

    # Extract text from Converse response
    text = response["output"]["message"]["content"][0]["text"]
    return text.strip()


# ── Public API ────────────────────────────────────────────────────────────────

def classify(prompt: str) -> str:
    """
    Used by classification_agent.py and intent_agent.py.
    Calls Nova Micro — fast and cheap for structured JSON classification tasks.

    Args:
        prompt: Full prompt string built by the agent

    Returns:
        Raw text response from the model (agents parse the JSON themselves)
    """
    try:
        result = _invoke_nova(CLASSIFY_MODEL, prompt, max_tokens=512)
        logger.info(f"[Bedrock] classify() — model={CLASSIFY_MODEL} response_len={len(result)}")
        return result
    except Exception as e:
        logger.error(f"[Bedrock] classify() failed: {e}")
        raise


def generate(prompt: str) -> str:
    """
    Used by explanation_agent.py.
    Calls Nova Lite — better at flowing prose for human-readable summaries.

    Args:
        prompt: Full prompt string built by the agent

    Returns:
        Raw text response from the model
    """
    try:
        result = _invoke_nova(GENERATE_MODEL, prompt, max_tokens=1024)
        logger.info(f"[Bedrock] generate() — model={GENERATE_MODEL} response_len={len(result)}")
        return result
    except Exception as e:
        logger.error(f"[Bedrock] generate() failed: {e}")
        raise


def get_embedding(text: str) -> list[float]:
    """
    Used by correlation_agent.py.
    Calls Titan Embeddings V2 — returns a 1024-dim vector.

    Args:
        text: Text to embed (translated English content)

    Returns:
        List of floats representing the embedding vector
    """
    try:
        response = bedrock.invoke_model(
            modelId=EMBED_MODEL,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "inputText": text,
            }),
        )

        result    = json.loads(response["body"].read())
        embedding = result.get("embedding")

        if not embedding:
            raise ValueError("Empty embedding returned from Titan")

        logger.info(f"[Bedrock] get_embedding() — dim={len(embedding)}")
        return embedding

    except Exception as e:
        logger.error(f"[Bedrock] get_embedding() failed: {e}")
        raise
