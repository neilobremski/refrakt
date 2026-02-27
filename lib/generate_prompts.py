#!/usr/bin/env python3
"""
generate_prompts.py

Reads enriched playlist data and generates Suno AI prompts for a random
selection of tracks that haven't been generated yet.

For each selected track:
  1. Researches the track's musical character via Perplexity AI (cached)
  2. Synthesizes a rich descriptive tag string from the research
  3. Generates structural metatags for the Lyrics field
  4. Invents an abstract title (NOT derived from the original track name)

Usage:
    .venv/bin/python generate_prompts.py [--count N] [--seed SEED]

Output: prompts_data.json
"""

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from perplexity import ask as perplexity_ask

BASE_DIR = Path(__file__).parent.parent
PLAYLIST_FILE = BASE_DIR / "playlist_data.json"
PROMPTS_FILE = BASE_DIR / "prompts_data.json"
GENERATED_FILE = BASE_DIR / "generated_tracks.json"
RESEARCH_CACHE_FILE = BASE_DIR / ".refrakt" / "caches" / "prompt_research.json"

# Suno model
SUNO_MODEL = "chirp-crow"

# Delay between Perplexity API calls to avoid rate limiting
API_DELAY = 1.5

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


def invent_title(rng: random.Random) -> str:
    """Generate an evocative, abstract title unrelated to any source track."""
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

def load_research_cache() -> dict:
    """Load the research cache from disk."""
    if RESEARCH_CACHE_FILE.exists():
        try:
            with open(RESEARCH_CACHE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_research_cache(cache: dict) -> None:
    """Write the research cache to disk."""
    RESEARCH_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RESEARCH_CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Perplexity research (Phase 1 & 2)
# ---------------------------------------------------------------------------

def research_track(track_name: str, artists: list[str], genres: list[str],
                   cache: dict) -> str:
    """
    Phase 1: Research a track's musical character via Perplexity.
    Returns cached result if available.
    """
    # Build a cache key from track name + artists
    cache_key = f"{track_name}||{'|'.join(artists)}"

    if cache_key in cache:
        return cache[cache_key]["research"]

    artist_str = ", ".join(artists)
    genre_hint = f" (genres: {', '.join(genres[:5])})" if genres else ""

    query = (
        f"Describe the musical style, sonic character, instrumentation, mood, "
        f"tempo, and production aesthetics of '{track_name}' by {artist_str}"
        f"{genre_hint}. "
        f"Focus on: specific instruments and sounds, production techniques, "
        f"tempo/BPM, emotional mood, sonic textures. "
        f"Be specific about sound design, not just genre labels. "
        f"Keep it under 200 words."
    )

    print(f"    Researching via Perplexity...")
    research = perplexity_ask(query)

    cache[cache_key] = {
        "research": research,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    save_research_cache(cache)

    return research


def synthesize_tags(research: str, genres: list[str], duration_ms: int) -> str:
    """
    Phase 2: Synthesize a rich Suno tag string from research + metadata.
    Uses Perplexity to distill the research into an optimized 120-200 char tag string.
    """
    # Estimate BPM from duration
    if duration_ms < 180_000:
        bpm_hint = "~130 BPM"
    elif duration_ms < 300_000:
        bpm_hint = "~100 BPM"
    elif duration_ms < 480_000:
        bpm_hint = "~75 BPM"
    else:
        bpm_hint = "~60 BPM"

    genre_str = ", ".join(genres[:3]) if genres else "electronic"

    query = (
        f"Given this description of a track:\n\n{research}\n\n"
        f"Write a Suno AI style prompt (120-200 characters) that captures "
        f"the sonic character. Include: 2-3 genre anchors from [{genre_str}], "
        f"specific sonic textures, mood/atmosphere descriptors, {bpm_hint}, "
        f"and 'instrumental'. Use descriptive phrases not just genre labels.\n\n"
        f"Example: 'deep space ambient, vast ethereal drones, slowly evolving "
        f"harmonic layers, shimmering cosmic pads, distant reverb tails, "
        f"55 BPM, instrumental'\n\n"
        f"Return ONLY the tag string, nothing else. No quotes, no explanation."
    )

    tags = perplexity_ask(query)

    # Clean up: strip quotes, newlines, explanatory text
    tags = tags.strip().strip('"').strip("'")
    # If the response has multiple lines, take only the first
    if "\n" in tags:
        tags = tags.split("\n")[0].strip()
    # Ensure 'instrumental' is present
    if "instrumental" not in tags.lower():
        tags = tags.rstrip(", ") + ", instrumental"

    return tags


# ---------------------------------------------------------------------------
# Structural metatags (Lyrics field)
# ---------------------------------------------------------------------------

# Genre keywords mapped to structural templates
STRUCTURE_TEMPLATES = {
    "ambient": "[Intro]\n[Slow Build]\n[Interlude]\n[Build]\n[Fade Out]\n[End]",
    "drone": "[Intro]\n[Slow Build]\n[Interlude]\n[Build]\n[Fade Out]\n[End]",
    "electronic": "[Atmospheric Intro]\n[Build]\n[Break]\n[Melodic Interlude]\n[Build]\n[Big Finish]\n[Fade To End]",
    "breakbeat": "[Atmospheric Intro]\n[Build]\n[Break]\n[Melodic Interlude]\n[Build]\n[Big Finish]\n[Fade To End]",
    "idm": "[Atmospheric Intro]\n[Build]\n[Break]\n[Melodic Interlude]\n[Build]\n[Big Finish]\n[Fade To End]",
    "trance": "[Atmospheric Intro]\n[Build]\n[Break]\n[Melodic Interlude]\n[Build]\n[Big Finish]\n[Fade To End]",
    "techno": "[Atmospheric Intro]\n[Build]\n[Break]\n[Melodic Interlude]\n[Build]\n[Big Finish]\n[Fade To End]",
}

DEFAULT_STRUCTURE = "[Intro]\n[Slow Build]\n[Break]\n[Build]\n[Instrumental Interlude]\n[Outro]\n[Fade To End]"


def build_structure(genres: list[str], duration_ms: int) -> str:
    """
    Choose a structural metatag template based on genre and duration.
    Longer tracks get the ambient template; electronic genres get the breakbeat template.
    """
    # Very long tracks → ambient structure regardless
    if duration_ms > 480_000:
        return STRUCTURE_TEMPLATES["ambient"]

    # Check genres for matches
    genres_lower = [g.lower() for g in genres]
    for keyword, template in STRUCTURE_TEMPLATES.items():
        for g in genres_lower:
            if keyword in g:
                return template

    return DEFAULT_STRUCTURE


# ---------------------------------------------------------------------------
# Tracking generated tracks
# ---------------------------------------------------------------------------

def load_generated() -> set:
    """Load the set of track IDs that have already been generated."""
    if GENERATED_FILE.exists():
        try:
            with open(GENERATED_FILE, "r") as f:
                data = json.load(f)
            return set(data.get("track_ids", []))
        except (json.JSONDecodeError, OSError):
            pass
    return set()


def save_generated(track_ids: set) -> None:
    """Save the set of generated track IDs."""
    with open(GENERATED_FILE, "w") as f:
        json.dump({"track_ids": sorted(track_ids)}, f, indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate Suno AI prompts from enriched playlist data."
    )
    parser.add_argument(
        "--count", type=int, default=10,
        help="Number of prompts to generate (default: 10)"
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for reproducibility (optional)"
    )
    args = parser.parse_args()

    # Load playlist
    if not PLAYLIST_FILE.exists():
        print(f"ERROR: {PLAYLIST_FILE} not found. Run fetch_playlist.py first.")
        sys.exit(1)

    with open(PLAYLIST_FILE, "r") as f:
        data = json.load(f)

    tracks = data.get("tracks", [])
    print(f"Loaded {len(tracks)} tracks from {PLAYLIST_FILE.name}")

    # Check for genres
    tracks_with_genres = [t for t in tracks if t.get("genres")]
    if not tracks_with_genres:
        print("WARNING: No tracks have genre tags. Run enrich_genres.py first.")
        print("Proceeding with metadata-only tags (less accurate).")

    # Load already-generated track IDs
    generated = load_generated()
    print(f"Already generated: {len(generated)} tracks")

    # Filter to ungenerated tracks
    available = [t for t in tracks if t["id"] not in generated]
    print(f"Available for generation: {len(available)} tracks")

    if not available:
        print("All tracks have been generated! Nothing to do.")
        sys.exit(0)

    count = min(args.count, len(available))
    print(f"Selecting {count} tracks at random...")

    # Random selection
    rng = random.Random(args.seed)
    selected = rng.sample(available, count)

    # Load research cache
    research_cache = load_research_cache()
    cache_hits = 0

    # Generate prompts
    prompts = []
    for i, track in enumerate(selected):
        track_name = track["name"]
        artists = track.get("artists", [])
        genres = track.get("genres", [])
        duration_ms = track.get("duration_ms", 0)

        print(f"\n[{i+1}/{count}] {track_name} ({', '.join(artists)})")

        # Phase 1: Research track
        cache_key = f"{track_name}||{'|'.join(artists)}"
        was_cached = cache_key in research_cache
        research = research_track(track_name, artists, genres, research_cache)
        if was_cached:
            cache_hits += 1
            print(f"    Research: cached")
        else:
            print(f"    Research: fetched from Perplexity")
            time.sleep(API_DELAY)

        # Phase 2: Synthesize rich tags
        print(f"    Synthesizing tags...")
        tags = synthesize_tags(research, genres, duration_ms)
        time.sleep(API_DELAY)

        # Build structural metatags for Lyrics field
        structure = build_structure(genres, duration_ms)

        # Invent title
        title = invent_title(rng)

        prompt = {
            "source_track_id": track["id"],
            "source_track_name": track_name,
            "source_artists": artists,
            "invented_title": title,
            "tags": tags,
            "negative_tags": "vocals, singing, voice, spoken word",
            "prompt": structure,
            "make_instrumental": True,
            "mv": SUNO_MODEL,
            "research": research,
        }
        prompts.append(prompt)

        print(f"    Title:     {title}")
        print(f"    Tags:      {tags}")
        print(f"    Neg. tags: vocals, singing, voice, spoken word")
        print(f"    Structure: {structure.split(chr(10))[0]}... ({len(structure.split(chr(10)))} sections)")

    # Write prompts
    with open(PROMPTS_FILE, "w") as f:
        json.dump(prompts, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"Written {len(prompts)} prompts to {PROMPTS_FILE.name}")
    print(f"Research cache: {cache_hits} hits, {count - cache_hits} new lookups")
    print(f"Next step: bin/suno-generate --count {count}")


if __name__ == "__main__":
    main()
