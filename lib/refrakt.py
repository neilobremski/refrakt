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

from genius import fetch_lyrics
from perplexity import ask as perplexity_ask

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

PROMPTS_FILE = BASE_DIR / "prompts_data.json"
RESEARCH_CACHE_FILE = BASE_DIR / ".prompt_research_cache.json"

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
    with open(RESEARCH_CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


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
        f"Focus on: specific instruments and sounds, production techniques, "
        f"tempo/BPM, emotional mood, sonic textures, and what the lyrics are about. "
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


def synthesize_tags(research, duration_ms):
    if duration_ms < 180_000:
        bpm_hint = "~130 BPM"
    elif duration_ms < 300_000:
        bpm_hint = "~100 BPM"
    elif duration_ms < 480_000:
        bpm_hint = "~75 BPM"
    else:
        bpm_hint = "~60 BPM"

    query = (
        f"Given this description of a track:\n\n{research}\n\n"
        f"Write a Suno AI style prompt (120-200 characters) that captures "
        f"the sonic character. Include: 2-3 genre anchors, specific sonic textures, "
        f"mood/atmosphere descriptors, {bpm_hint}. Do NOT include 'instrumental' — "
        f"this song has vocals. Use descriptive phrases not just genre labels.\n\n"
        f"Example: 'art rock, chamber pop, hypnotic cyclical dissonance, "
        f"glockenspiel clashes, sparse moody intimacy, anthemic vocals, 100 BPM'\n\n"
        f"Return ONLY the tag string, nothing else. No quotes, no explanation."
    )

    print(f"    Synthesizing tags via Perplexity...")
    tags = perplexity_ask(query)

    tags = tags.strip().strip('"').strip("'")
    if "\n" in tags:
        tags = tags.split("\n")[0].strip()

    return tags


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

    # Connect to Spotify
    print(f"Connecting to Spotify...")
    sp = get_spotify_client()
    user = sp.current_user()
    print(f"Logged in as: {user['display_name']}")

    # Find playlist
    print(f"Looking for playlist: '{args.playlist}'...")
    playlist = find_playlist(sp, args.playlist)
    if not playlist:
        print(f"ERROR: Could not find playlist '{args.playlist}'")
        sys.exit(1)
    print(f"Found: '{playlist['name']}' ({playlist['id']})")

    # Fetch tracks
    print(f"Fetching tracks...")
    tracks = get_playlist_tracks(sp, playlist["id"], limit=500)
    print(f"  {len(tracks)} tracks loaded")

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
            print(f"ERROR: No track matching '{args.track}' found")
            sys.exit(1)
        track = matches[0]
        if len(matches) > 1:
            print(f"  Multiple matches, using first: '{track['name']}'")
    elif args.index is not None:
        idx = args.index - 1
        if idx < 0 or idx >= len(tracks):
            print(f"ERROR: Index {args.index} out of range (1-{len(tracks)})")
            sys.exit(1)
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

    # Synthesize tags
    tags = synthesize_tags(research, duration_ms)
    time.sleep(API_DELAY)

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

    with open(PROMPTS_FILE, "w") as f:
        json.dump(prompt, f, indent=2, ensure_ascii=False)

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
