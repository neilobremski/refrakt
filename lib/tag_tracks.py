#!/usr/bin/env python3
"""
tag_tracks.py — Tag downloaded M4A files with Suno clip metadata.

Writes MP4 atoms (title, artist, album, genre, year, comment, description, cover art)
using data from the Suno feed API and prompts_data.json.

Usage (standalone):
    .venv/bin/python lib/tag_tracks.py --all              # retro-tag all files in output/
    .venv/bin/python lib/tag_tracks.py --all --dry-run     # preview without writing
    .venv/bin/python lib/tag_tracks.py <clip_id> ...       # tag specific clips
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import requests
from mutagen.mp4 import MP4, MP4Cover

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = _BASE_DIR / "output"
PROMPTS_FILE = _BASE_DIR / "prompts_data.json"
CDN_BASE = "https://cdn1.suno.ai"
ALBUM_NAME = "Wordless Work (Suno)"
ARTIST_NAME = "Refrakt"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_clip_prefix(filename: str) -> str | None:
    """Extract the 8-char clip ID prefix from a filename like '..._{title}__{clip_id}.m4a'."""
    m = re.search(r"__([0-9a-f]{8})\.m4a$", filename)
    return m.group(1) if m else None


def find_m4a_files(directory: Path) -> list[Path]:
    """Return all .m4a files in directory, sorted by name."""
    return sorted(directory.glob("*.m4a"))


def download_cover_art(image_url: str) -> bytes | None:
    """Download JPEG cover art from Suno CDN. Returns bytes or None on failure."""
    try:
        r = requests.get(image_url, timeout=15)
        r.raise_for_status()
        return r.content
    except Exception as e:
        print(f"  WARNING: Could not download cover art: {e}")
        return None


def load_prompts() -> list[dict]:
    """Load prompts_data.json if it exists."""
    if not PROMPTS_FILE.exists():
        return []
    with open(PROMPTS_FILE) as f:
        return json.load(f)


def match_prompt_to_clip(clip: dict, prompts: list[dict]) -> dict | None:
    """Match a clip to its source prompt entry by title."""
    clip_title = clip.get("title", "").strip().lower()
    if not clip_title:
        return None
    for p in prompts:
        if p.get("invented_title", "").strip().lower() == clip_title:
            return p
    return None


# ---------------------------------------------------------------------------
# Core tagging
# ---------------------------------------------------------------------------

def tag_file(filepath: str | Path, clip: dict, prompt: dict | None = None) -> None:
    """Write MP4 metadata atoms to an M4A file.

    Args:
        filepath: Path to the .m4a file.
        clip: Suno feed clip dict (must have id, title, metadata, created_at, etc.).
        prompt: Optional prompts_data.json entry for source track info.
    """
    audio = MP4(str(filepath))

    clip_id = clip.get("id", "")
    title = clip.get("title", "")
    metadata = clip.get("metadata", {}) or {}
    tags_str = metadata.get("tags", "")
    created_at = clip.get("created_at", "")
    model_name = clip.get("model_name", "")

    # Core atoms
    audio["\xa9nam"] = [title]                     # Title
    audio["\xa9ART"] = [ARTIST_NAME]               # Artist
    audio["\xa9alb"] = [ALBUM_NAME]                # Album
    if tags_str:
        audio["\xa9gen"] = [tags_str]              # Genre
    if created_at:
        audio["\xa9day"] = [created_at[:4]]        # Year

    # Comment: suno:{clip_id} model:{model_name}
    comment_parts = []
    if clip_id:
        comment_parts.append(f"suno:{clip_id}")
    if model_name:
        comment_parts.append(f"model:{model_name}")
    if comment_parts:
        audio["\xa9cmt"] = [" ".join(comment_parts)]

    # Description: source track info from prompts_data.json
    if prompt:
        source_name = prompt.get("source_track_name", "")
        source_artists = prompt.get("source_artists", [])
        if source_name:
            artists_str = ", ".join(source_artists) if source_artists else "Unknown"
            audio["desc"] = [f"Inspired by: {source_name} by {artists_str}"]

    # Cover art
    image_url = clip.get("image_large_url") or clip.get("image_url")
    if image_url:
        art_data = download_cover_art(image_url)
        if art_data:
            audio["covr"] = [MP4Cover(art_data, imageformat=MP4Cover.FORMAT_JPEG)]

    audio.save()


# ---------------------------------------------------------------------------
# Feed fetching (for retro-tagging)
# ---------------------------------------------------------------------------

def _fetch_all_feed_clips(max_pages: int = 10) -> list[dict]:
    """Fetch clip data from Suno feed, up to max_pages pages."""
    # Lazy import to avoid circular dependency and keep suno.py optional
    sys.path.insert(0, str(_BASE_DIR / "lib"))
    from suno import load_session, refresh_jwt, get_feed

    session = load_session()
    jwt = refresh_jwt(session)

    all_clips = []
    for page in range(max_pages):
        clips = get_feed(session, jwt, page=page)
        if not clips:
            break
        all_clips.extend(clips)
    return all_clips


def _build_clip_index(clips: list[dict]) -> dict[str, dict]:
    """Build a dict mapping 8-char clip ID prefix -> full clip dict."""
    index = {}
    for clip in clips:
        full_id = clip.get("id", "")
        if len(full_id) >= 8:
            index[full_id[:8]] = clip
    return index


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Tag M4A files with Suno clip metadata.",
    )
    parser.add_argument("clip_ids", nargs="*", metavar="clip_id",
                        help="Specific clip ID prefixes to tag")
    parser.add_argument("--all", action="store_true",
                        help="Tag all .m4a files in output/")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview what would be tagged without writing")
    args = parser.parse_args()

    if not args.all and not args.clip_ids:
        parser.error("Provide clip IDs or use --all")

    # Find files to tag
    m4a_files = find_m4a_files(OUTPUT_DIR)
    if not m4a_files:
        print("No .m4a files found in output/")
        return

    # Filter to requested clip IDs if specified
    if args.clip_ids:
        requested = set(args.clip_ids)
        filtered = []
        for f in m4a_files:
            prefix = extract_clip_prefix(f.name)
            if prefix and prefix in requested:
                filtered.append(f)
        m4a_files = filtered

    if not m4a_files:
        print("No matching .m4a files found.")
        return

    print(f"Found {len(m4a_files)} file(s) to tag.\n")

    # Fetch feed data for clip metadata
    print("Fetching clip metadata from Suno feed...")
    all_clips = _fetch_all_feed_clips()
    clip_index = _build_clip_index(all_clips)
    print(f"  Loaded {len(all_clips)} clips from feed.\n")

    # Load prompts for source track info
    prompts = load_prompts()
    if prompts:
        print(f"Loaded {len(prompts)} prompts from prompts_data.json.\n")

    tagged = 0
    skipped = 0

    for filepath in m4a_files:
        prefix = extract_clip_prefix(filepath.name)
        if not prefix:
            print(f"  SKIP {filepath.name} — could not extract clip ID")
            skipped += 1
            continue

        clip = clip_index.get(prefix)
        if not clip:
            print(f"  SKIP {filepath.name} — clip {prefix}... not found in feed")
            skipped += 1
            continue

        prompt = match_prompt_to_clip(clip, prompts)

        title = clip.get("title", "?")
        tags = (clip.get("metadata") or {}).get("tags", "")
        has_art = bool(clip.get("image_large_url") or clip.get("image_url"))
        source = ""
        if prompt:
            source = f" (from: {prompt.get('source_track_name', '?')})"

        if args.dry_run:
            print(f"  DRY-RUN {filepath.name}")
            print(f"    Title:  {title}")
            print(f"    Genre:  {tags}")
            print(f"    Art:    {'yes' if has_art else 'no'}")
            print(f"    Source: {source or 'no match'}")
        else:
            try:
                tag_file(filepath, clip, prompt)
                print(f"  TAGGED  {filepath.name} — {title}{source}")
                tagged += 1
            except Exception as e:
                print(f"  ERROR   {filepath.name} — {e}")
                skipped += 1

    print(f"\nDone. Tagged: {tagged}, Skipped: {skipped}")


if __name__ == "__main__":
    main()
