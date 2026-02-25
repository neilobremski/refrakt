"""
perplexity.py

Thin wrapper around the Perplexity REST API (chat completions endpoint).
Loads PERPLEXITY_API_KEY from .env and exposes a single `ask()` function.
"""

import os
import sys
from pathlib import Path

import requests

BASE_DIR = Path(__file__).parent.parent
_API_URL = "https://api.perplexity.ai/chat/completions"
_MODEL = "sonar-pro"
_TIMEOUT = 30


def _load_api_key() -> str:
    """Load PERPLEXITY_API_KEY from environment or .env file."""
    key = os.environ.get("PERPLEXITY_API_KEY")
    if key:
        return key

    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("PERPLEXITY_API_KEY="):
                return line.split("=", 1)[1].strip()

    print("ERROR: PERPLEXITY_API_KEY not found in environment or .env", file=sys.stderr)
    sys.exit(1)


def ask(query: str) -> str:
    """
    Send a query to Perplexity's chat completions API and return the text response.

    Uses the sonar-pro model with web search grounding.
    """
    api_key = _load_api_key()

    resp = requests.post(
        _API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": _MODEL,
            "messages": [{"role": "user", "content": query}],
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()

    data = resp.json()
    return data["choices"][0]["message"]["content"]
