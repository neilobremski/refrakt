#!/usr/bin/env python3
"""
enrich_genres.py

Enriches playlist_data.json with genre tags sourced from the Last.fm API.

For each unique artist in the playlist, queries Last.fm's artist.getTopTags
endpoint and stores the top genre tags. Those tags are then written back to
every matching track as a `genres` list field.

Results are cached to .refrakt/caches/lastfm.json so the script is safe to re-run
without hammering the API.

Usage:
    .venv/bin/python enrich_genres.py

Requirements:
    - LASTFM_API_KEY set in .env
    - playlist_data.json present in the same directory
"""

import json
import os
import time
import re
import sys
from pathlib import Path
from dotenv import load_dotenv
import requests

load_dotenv(Path(__file__).parent.parent / ".env")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent
INPUT_FILE = BASE_DIR / "playlist_data.json"
OUTPUT_FILE = BASE_DIR / "playlist_data.json"  # in-place update
CACHE_FILE = BASE_DIR / ".refrakt" / "caches" / "lastfm.json"

# ---------------------------------------------------------------------------
# Last.fm config
# ---------------------------------------------------------------------------
LASTFM_API_KEY = os.environ.get("LASTFM_API_KEY", "")
LASTFM_API_URL = "https://ws.audioscrobbler.com/2.0/"
REQUEST_DELAY = 0.2  # seconds between API calls (~5 req/s max per docs)
TOP_TAGS_LIMIT = 5   # how many top tags to keep per artist

# ---------------------------------------------------------------------------
# Tags to strip — non-genre / meta-descriptors / personal tags
# ---------------------------------------------------------------------------
# These are matched case-insensitively against each tag name.
BLOCKLIST_EXACT = {
    "seen live",
    "favorites",
    "favourite",
    "favourites",
    "my favourites",
    "love",
    "loved",
    "loved tracks",
    "amazing",
    "beautiful",
    "awesome",
    "good",
    "great",
    "best",
    "cool",
    "nice",
    "perfect",
    "recommended",
    "check out",
    "to listen",
    "to hear",
    "heard of",
    "under 2000 listeners",
    "spotify",
    "youtube",
    "soundcloud",
    "bandcamp",
    "all",
    "music",
    "songs",
    "tracks",
}

# Patterns that identify obviously-non-genre tags (pure numbers, star ratings, etc.)
# Note: decade strings like "80s" and "90s" ARE useful genre descriptors, so we
# deliberately do NOT block them here.
BLOCKLIST_PATTERNS = [
    re.compile(r"^\d+$"),              # bare integers with no letter suffix
    re.compile(r"^[\d\s\-\*\/]+$"),    # strings that are only digits/stars/dashes
    re.compile(r"^\d{4}$"),            # four-digit years e.g. "2003"
]


def is_genre_tag(tag_name: str) -> bool:
    """Return True if the tag looks like a genuine genre/style descriptor."""
    lowered = tag_name.strip().lower()

    # Blocklist exact match
    if lowered in BLOCKLIST_EXACT:
        return False

    # Blocklist pattern match
    for pattern in BLOCKLIST_PATTERNS:
        if pattern.match(lowered):
            return False

    # Must have at least 2 characters
    if len(lowered) < 2:
        return False

    return True


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def load_cache() -> dict:
    """Load the artist-to-tags cache from disk, or return an empty dict."""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: could not load cache ({e}), starting fresh.")
    return {}


def save_cache(cache: dict) -> None:
    """Persist the cache to disk."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Last.fm API
# ---------------------------------------------------------------------------

def fetch_artist_tags(artist_name: str) -> list[str]:
    """
    Query Last.fm artist.getTopTags and return a filtered list of genre tags.

    Returns an empty list on any error (artist not found, network issue, etc.).
    """
    params = {
        "method": "artist.getTopTags",
        "artist": artist_name,
        "api_key": LASTFM_API_KEY,
        "format": "json",
        "autocorrect": 1,
    }

    try:
        resp = requests.get(LASTFM_API_URL, params=params, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"    HTTP error for '{artist_name}': {e}")
        return []

    data = resp.json()

    # Last.fm returns {"error": N, "message": "..."} for unknown artists
    if "error" in data:
        msg = data.get("message", "")
        # Error 6 = Artist not found; treat silently; others worth noting
        if data["error"] != 6:
            print(f"    Last.fm error {data['error']} for '{artist_name}': {msg}")
        return []

    raw_tags = data.get("toptags", {}).get("tag", [])
    if not raw_tags:
        return []

    # raw_tags is a list of {"name": ..., "count": ..., "url": ...}
    # They arrive in descending count order; take the first TOP_TAGS_LIMIT
    # after filtering.
    filtered = []
    for tag in raw_tags:
        name = tag.get("name", "").strip()
        if is_genre_tag(name):
            filtered.append(name)
        if len(filtered) >= TOP_TAGS_LIMIT:
            break

    return filtered


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # --- Validate API key ---------------------------------------------------
    if not LASTFM_API_KEY:
        print("ERROR: LASTFM_API_KEY is not set in .env")
        print("  Add your Last.fm API key to .env:")
        print("  LASTFM_API_KEY=your_key_here")
        print("  Get a free key at: https://www.last.fm/api/account/create")
        sys.exit(1)

    # --- Load playlist data -------------------------------------------------
    if not INPUT_FILE.exists():
        print(f"ERROR: {INPUT_FILE} not found. Run fetch_playlist.py first.")
        sys.exit(1)

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    tracks = data.get("tracks", [])
    print(f"Loaded {len(tracks)} tracks from {INPUT_FILE.name}")

    # --- Collect unique artists (preserving first-seen order) ---------------
    seen = set()
    unique_artists = []
    for track in tracks:
        for artist in track.get("artists", []):
            if artist not in seen:
                seen.add(artist)
                unique_artists.append(artist)

    total_artists = len(unique_artists)
    print(f"Found {total_artists} unique artists")

    # --- Load cache ---------------------------------------------------------
    cache = load_cache()
    cached_count = sum(1 for a in unique_artists if a in cache)
    print(f"Cache: {cached_count}/{total_artists} artists already cached")
    print()

    # --- Fetch tags for artists not in cache --------------------------------
    for i, artist in enumerate(unique_artists, start=1):
        if artist in cache:
            tags = cache[artist]
            print(f"Artist {i}/{total_artists}: {artist} → {tags}  (cached)")
            continue

        tags = fetch_artist_tags(artist)
        cache[artist] = tags
        print(f"Artist {i}/{total_artists}: {artist} → {tags}")

        # Persist cache after every fetch so progress survives interruption
        save_cache(cache)

        time.sleep(REQUEST_DELAY)

    print()
    print("All artists processed. Building enriched track records...")

    # --- Enrich tracks with genres ------------------------------------------
    for track in tracks:
        # Collect the union of genre tags from all artists on the track
        genres_union = []
        seen_tags = set()
        for artist in track.get("artists", []):
            for tag in cache.get(artist, []):
                tag_lower = tag.lower()
                if tag_lower not in seen_tags:
                    seen_tags.add(tag_lower)
                    genres_union.append(tag)
        track["genres"] = genres_union

    # --- Write enriched data back to file -----------------------------------
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Written enriched data to {OUTPUT_FILE.name}")

    # --- Summary stats ------------------------------------------------------
    tracks_with_genres = sum(1 for t in tracks if t.get("genres"))
    tracks_without_genres = len(tracks) - tracks_with_genres
    print()
    print("Summary:")
    print(f"  Tracks with genres:    {tracks_with_genres}")
    print(f"  Tracks without genres: {tracks_without_genres}")
    print()
    print("Sample (first 3 enriched tracks):")
    for track in tracks[:3]:
        print(f"  {track['name']} — {track['artists']} → {track.get('genres', [])}")


if __name__ == "__main__":
    main()
