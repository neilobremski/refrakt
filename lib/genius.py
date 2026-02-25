"""
genius.py

Fetches song lyrics from Genius via the lyricsgenius library.
Loads GENIUS_ACCESS_TOKEN from .env.
"""

import os
import sys
from pathlib import Path

import lyricsgenius

BASE_DIR = Path(__file__).parent.parent


def _load_token() -> str:
    token = os.environ.get("GENIUS_ACCESS_TOKEN")
    if token:
        return token

    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("GENIUS_ACCESS_TOKEN="):
                return line.split("=", 1)[1].strip()

    print("ERROR: GENIUS_ACCESS_TOKEN not found in environment or .env", file=sys.stderr)
    sys.exit(1)


def fetch_lyrics(track_name: str, artist: str) -> str | None:
    """
    Fetch lyrics for a track from Genius.

    Returns the lyrics text (with structure tags like [Verse 1], [Chorus], etc.)
    or None if not found.
    """
    token = _load_token()
    genius = lyricsgenius.Genius(token, verbose=False, remove_section_headers=False)
    genius.excluded_terms = ["(Remix)", "(Live)"]

    try:
        song = genius.search_song(track_name, artist)
    except Exception as e:
        print(f"WARNING: Genius API error for '{track_name}': {e}", file=sys.stderr)
        return None
    if song and song.lyrics:
        return song.lyrics.strip()
    return None
