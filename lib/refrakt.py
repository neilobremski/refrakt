#!/usr/bin/env python3
"""
refrakt.py

Refrakt — create original songs refracted from existing ones.

Fetches a track from any Spotify playlist, pulls original lyrics from Genius,
researches its sonic character via Perplexity, synthesizes rich tags, and writes
prompts_data.json. The refracted lyrics are generated separately by the Refrakt
agent (Haiku model).

Usage:
    bin/refrakt --playlist "Rocket" --track "Retrovertigo"
    bin/refrakt --playlist "Rocket" --random
    bin/refrakt --playlist "Rocket" --index 3
    bin/refrakt --playlist "Rocket" --list --random
"""

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Ensure lib/ is on sys.path so sibling module imports resolve regardless of invocation path
_LIB_DIR = Path(__file__).parent
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from genius import fetch_lyrics
from perplexity import ask as perplexity_ask

BASE_DIR = _LIB_DIR.parent
load_dotenv(BASE_DIR / ".env")

PROMPTS_FILE = BASE_DIR / "prompts_data.json"
RESEARCH_CACHE_FILE = BASE_DIR / ".prompt_research_cache.json"
PLAYLIST_CACHE_FILE = BASE_DIR / ".playlist_cache.json"
PLAYLIST_CACHE_TTL = 24 * 60 * 60  # 24 hours in seconds

SUNO_MODEL = "chirp-crow"
API_DELAY = 1.5

# ---------------------------------------------------------------------------
# Spotify helpers
# ---------------------------------------------------------------------------

def get_spotify_client():
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=os.environ["SPOTIFY_CLIENT_ID"],
        client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
        redirect_uri=os.environ["SPOTIFY_REDIRECT_URI"],
        scope="playlist-read-private playlist-read-collaborative",
        open_browser=False,
    ))


def find_playlist(sp, name):
    offset = 0
    while True:
        result = sp.current_user_playlists(limit=50, offset=offset)
        for playlist in result["items"]:
            if playlist["name"].lower() == name.lower():
                return playlist
        if result["next"] is None:
            break
        offset += 50
    return None


def get_playlist_tracks(sp, playlist_id, limit=100):
    tracks = []
    offset = 0
    while len(tracks) < limit:
        result = sp._get(f"playlists/{playlist_id}/items", limit=min(100, limit - len(tracks)), offset=offset)
        for item in result["items"]:
            track = item.get("item")
            if track and track.get("id") and track.get("type") == "track":
                tracks.append({
                    "id": track["id"],
                    "name": track["name"],
                    "artists": [a["name"] for a in track["artists"]],
                    "album": track["album"]["name"],
                    "release_year": (track["album"].get("release_date") or "")[:4],
                    "duration_ms": track["duration_ms"],
                })
        if result["next"] is None:
            break
        offset += len(result["items"])
    return tracks


# ---------------------------------------------------------------------------
# Playlist cache
# ---------------------------------------------------------------------------

def _load_playlist_cache():
    if PLAYLIST_CACHE_FILE.exists():
        try:
            with open(PLAYLIST_CACHE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_playlist_cache(cache):
    try:
        tmp = PLAYLIST_CACHE_FILE.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
        tmp.rename(PLAYLIST_CACHE_FILE)
    except OSError as e:
        print(f"WARNING: Could not write playlist cache: {e}", file=sys.stderr)


def get_cached_playlist(playlist_name):
    """Return (playlist_id, tracks) from cache if fresh, else None."""
    cache = _load_playlist_cache()
    key = playlist_name.lower()
    if key in cache:
        entry = cache[key]
        try:
            fetched_at = datetime.fromisoformat(entry["fetched_at"])
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - fetched_at).total_seconds()
            if age < PLAYLIST_CACHE_TTL:
                return entry["playlist_id"], entry["tracks"]
        except (KeyError, ValueError):
            pass
    return None


def save_playlist_to_cache(playlist_name, playlist_id, tracks):
    """Save playlist tracks to cache with current timestamp."""
    cache = _load_playlist_cache()
    cache[playlist_name.lower()] = {
        "playlist_name": playlist_name,
        "playlist_id": playlist_id,
        "tracks": tracks,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "track_count": len(tracks),
    }
    _save_playlist_cache(cache)


# ---------------------------------------------------------------------------
# Title invention
# ---------------------------------------------------------------------------

TITLE_WORDS_A = [
    "Hollow", "Glass", "Velvet", "Frozen", "Distant", "Silent",
    "Amber", "Copper", "Fading", "Floating", "Broken", "Hidden",
    "Pale", "Deep", "Slow", "Outer", "Inner", "Lost", "Warm",
    "Cold", "Soft", "Dark", "Bright", "Still", "Thin", "Wide",
    "Low", "High", "Long", "Brief", "Half", "Late", "Last",
    "Drifting", "Burning", "Falling", "Rising", "Waking", "Sleeping",
    "Sunken", "Crystal", "Iron", "Silver", "Golden", "Ashen",
    "Lunar", "Solar", "Tidal", "Coastal", "Northern", "Western",
    "Phantom", "Ghost", "Shadow", "Muted", "Quiet", "Calm",
    "Gentle", "Faint", "Sparse", "Dense", "Subtle", "Vivid",
]

TITLE_WORDS_B = [
    "Transit", "Quarter", "Signal", "Archive", "Passage", "Circuit",
    "Corridor", "Meridian", "Station", "Harbor", "Plateau", "Canyon",
    "Margin", "Threshold", "Beacon", "Horizon", "Expanse", "Lattice",
    "Gradient", "Contour", "Vessel", "Residue", "Fragment", "Remnant",
    "Outline", "Surface", "Symmetry", "Frequency", "Resonance", "Current",
    "Orbit", "Axis", "Vertex", "Prism", "Aperture", "Membrane",
    "Terrain", "Estuary", "Solstice", "Equinox", "Tempest", "Mirage",
    "Monument", "Pavilion", "Atrium", "Alcove", "Canopy", "Cradle",
    "Ember", "Drift", "Haze", "Bloom", "Pulse", "Wave",
    "Arc", "Veil", "Edge", "Layer", "Field", "Shore",
]

TITLE_CONNECTORS = ["of", "in", "on", "at", "by", "and", "for", "from"]


def invent_title(rng):
    style = rng.random()
    if style < 0.15:
        a = rng.choice(TITLE_WORDS_B)
        conn = rng.choice(TITLE_CONNECTORS)
        b = rng.choice(TITLE_WORDS_B)
        if a == b:
            b = rng.choice(TITLE_WORDS_B)
        return f"{a} {conn} {b}"
    elif style < 0.30:
        return rng.choice(TITLE_WORDS_B)
    else:
        a = rng.choice(TITLE_WORDS_A)
        b = rng.choice(TITLE_WORDS_B)
        return f"{a} {b}"


# ---------------------------------------------------------------------------
# Research cache
# ---------------------------------------------------------------------------

def load_research_cache():
    if RESEARCH_CACHE_FILE.exists():
        try:
            with open(RESEARCH_CACHE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_research_cache(cache):
    try:
        with open(RESEARCH_CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except OSError as e:
        print(f"WARNING: Could not write research cache: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Perplexity research + tag synthesis
# ---------------------------------------------------------------------------

def research_track(track_name, artists, cache):
    cache_key = f"{track_name}||{'|'.join(artists)}"

    if cache_key in cache:
        return cache[cache_key]["research"]

    artist_str = ", ".join(artists)
    query = (
        f"Describe the musical style, sonic character, instrumentation, mood, "
        f"tempo, and production aesthetics of '{track_name}' by {artist_str}. "
        f"Also describe the lyrical themes, emotional arc, and subject matter. "
        f"Describe the singer's vocal characteristics in detail: gender, vocal range "
        f"(bass/baritone/tenor/alto/soprano), tone quality (raspy, smooth, breathy, "
        f"gravelly, clear, etc.), delivery style (belting, crooning, falsetto, etc.), "
        f"and any distinctive vocal traits. "
        f"Focus on: specific instruments and sounds, production techniques, "
        f"tempo/BPM, emotional mood, sonic textures, vocal character, "
        f"and what the lyrics are about. "
        f"Be specific about sound design, not just genre labels. "
        f"Keep it under 250 words."
    )

    print(f"    Researching via Perplexity...")
    research = perplexity_ask(query)

    cache[cache_key] = {
        "research": research,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    save_research_cache(cache)
    return research


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Refrakt — create an original song refracted from a playlist track."
    )
    parser.add_argument(
        "--playlist", required=True,
        help="Spotify playlist name to pick from"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--track",
        help="Track name to search for (fuzzy match)"
    )
    group.add_argument(
        "--index", type=int,
        help="Track index (1-based) from the playlist"
    )
    group.add_argument(
        "--random", action="store_true",
        help="Pick a random track"
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for reproducibility"
    )
    parser.add_argument(
        "--list", action="store_true", dest="list_tracks",
        help="List tracks in the playlist and exit"
    )
    args = parser.parse_args()

    rng = random.Random(args.seed)

    # Check playlist cache first (avoids Spotify API calls if fresh)
    cached = get_cached_playlist(args.playlist)
    if cached is not None:
        playlist_id, tracks = cached
        print(f"Playlist '{args.playlist}' loaded from cache ({len(tracks)} tracks)")
    else:
        # Connect to Spotify
        print(f"Connecting to Spotify...")
        try:
            sp = get_spotify_client()
            user = sp.current_user()
        except Exception as e:
            sys.exit(f"ERROR: Spotify connection failed: {e}")
        print(f"Logged in as: {user['display_name']}")

        # Find playlist
        print(f"Looking for playlist: '{args.playlist}'...")
        try:
            playlist = find_playlist(sp, args.playlist)
        except Exception as e:
            sys.exit(f"ERROR: Spotify API call failed: {e}")
        if not playlist:
            sys.exit(f"ERROR: Could not find playlist '{args.playlist}'")
        playlist_id = playlist["id"]
        print(f"Found: '{playlist['name']}' ({playlist_id})")

        # Fetch tracks
        print(f"Fetching tracks...")
        try:
            tracks = get_playlist_tracks(sp, playlist_id, limit=500)
        except Exception as e:
            sys.exit(f"ERROR: Failed to fetch tracks: {e}")
        print(f"  {len(tracks)} tracks loaded")

        # Cache for next time
        save_playlist_to_cache(args.playlist, playlist_id, tracks)
        print(f"  Cached to {PLAYLIST_CACHE_FILE.name}")

    # List mode
    if args.list_tracks:
        for i, t in enumerate(tracks):
            dur = t["duration_ms"] // 1000
            artists = ", ".join(t["artists"])
            print(f"  {i+1:3d}. {t['name']} — {artists} ({dur//60}:{dur%60:02d})")
        return

    # Select track
    if args.track:
        search = args.track.lower()
        matches = [t for t in tracks if search in t["name"].lower()]
        if not matches:
            sys.exit(f"ERROR: No track matching '{args.track}' found")
        track = matches[0]
        if len(matches) > 1:
            print(f"  Multiple matches, using first: '{track['name']}'")
    elif args.index is not None:
        idx = args.index - 1
        if idx < 0 or idx >= len(tracks):
            sys.exit(f"ERROR: Index {args.index} out of range (1-{len(tracks)})")
        track = tracks[idx]
    else:  # --random
        track = rng.choice(tracks)

    track_name = track["name"]
    artists = track["artists"]
    duration_ms = track["duration_ms"]
    dur = duration_ms // 1000
    print(f"\nSelected: {track_name} — {', '.join(artists)} ({dur//60}:{dur%60:02d})")

    # Fetch original lyrics from Genius
    print(f"    Fetching lyrics from Genius...")
    original_lyrics = fetch_lyrics(track_name, artists[0])
    if original_lyrics:
        print(f"    Lyrics: found ({len(original_lyrics)} chars)")
    else:
        print(f"    Lyrics: not found on Genius")

    # Research
    cache = load_research_cache()
    cache_key = f"{track_name}||{'|'.join(artists)}"
    was_cached = cache_key in cache
    research = research_track(track_name, artists, cache)
    if was_cached:
        print(f"    Research: cached")
    else:
        print(f"    Research: fetched")
        time.sleep(API_DELAY)

    # Tags left empty — the suno-prompt agent handles tag generation
    # with access to the vocal prompting guide for richer vocal descriptors
    tags = ""

    # Invent title
    title = invent_title(rng)

    # Build prompt — original_lyrics + research provide the creative brief
    # The prompt field is left empty; the Refrakt agent writes refracted lyrics
    prompt = [{
        "source_track_id": track["id"],
        "source_track_name": track_name,
        "source_artists": artists,
        "source_playlist": args.playlist,
        "invented_title": title,
        "tags": tags,
        "negative_tags": "",
        "prompt": "",
        "original_lyrics": original_lyrics or "",
        "make_instrumental": False,
        "mv": SUNO_MODEL,
        "research": research,
    }]

    try:
        with open(PROMPTS_FILE, "w") as f:
            json.dump(prompt, f, indent=2, ensure_ascii=False)
    except OSError as e:
        sys.exit(f"ERROR: Could not write {PROMPTS_FILE}: {e}")

    print(f"\n{'='*60}")
    print(f"  REFRAKT")
    print(f"  Title:    {title}")
    print(f"  Tags:     {tags}")
    if original_lyrics:
        lines = original_lyrics.strip().split("\n")
        print(f"  Lyrics:   {len(lines)} lines fetched from Genius")
    else:
        print(f"  Lyrics:   not available")
    print(f"{'='*60}")
    print(f"\nWritten to {PROMPTS_FILE.name}")
    print(f"Next: spawn the Refrakt agent to write refracted lyrics")


if __name__ == "__main__":
    main()
