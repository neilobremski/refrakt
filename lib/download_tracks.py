#!/usr/bin/env python3
"""
download_tracks.py

Downloads completed Suno clips to the output/ directory.

Uses .m4a (Opus ~143 kbps) by default — this is what the Suno web player streams
and is significantly higher quality than the .mp3 audio_url (64 kbps) returned by
the API. Both CDN URLs are publicly accessible without auth.

Usage:
    .venv/bin/python download_tracks.py <clip_id> [<clip_id> ...]
    .venv/bin/python download_tracks.py        # uses DEFAULT_CLIP_IDS below

Auth is read from .refrakt/suno_session.json (see .gitignore).
The JWT is auto-refreshed via the Clerk token endpoint.
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
import requests

_BASE_DIR = Path(__file__).parent.parent
SESSION_FILE = str(_BASE_DIR / ".refrakt" / "suno_session.json")
OUTPUT_DIR = str(_BASE_DIR / "output")

# Hardcoded clip IDs from the initial test generation (2026-02-24).
# Pass IDs on the command line to override.
DEFAULT_CLIP_IDS = [
    "3aceca01-ec25-4b68-9e83-d409bd0f32bb",
    "61b399eb-310a-4ab4-a740-b87e93657b81",
]


def load_session():
    with open(SESSION_FILE) as f:
        return json.load(f)


def refresh_jwt(session):
    """Exchange the long-lived __client token for a fresh short-lived JWT."""
    session_id = session["session_id"]
    client_token = session["client_token"]
    url = f"https://auth.suno.com/v1/client/sessions/{session_id}/tokens"
    r = requests.post(
        url,
        headers={
            "Cookie": f"__client={client_token}",
            "Origin": "https://suno.com",
        },
        params={"_clerk_js_version": "5.36.2"},
    )
    r.raise_for_status()
    return r.json()["jwt"]


def poll_clips(clip_ids, jwt, django_session):
    """Fetch clip info from the feed endpoint."""
    ids_param = ",".join(clip_ids)
    r = requests.get(
        f"https://studio-api.prod.suno.com/api/feed/?ids={ids_param}",
        headers={
            "Authorization": f"Bearer {jwt}",
            "Cookie": f"sessionid={django_session}",
        },
    )
    r.raise_for_status()
    return r.json()


def sanitize_filename(name):
    """Convert a title to a safe filename (no path separators or special chars)."""
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = name.strip().replace(" ", "_")
    return name


def download_audio(url, dest_path):
    """Stream-download audio to dest_path."""
    r = requests.get(url, stream=True)
    r.raise_for_status()
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=65536):
            f.write(chunk)


def wait_for_completion(clip_ids, jwt, django_session, timeout=300, interval=5):
    """Poll until all clips are complete (or error/timeout)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        clips = poll_clips(clip_ids, jwt, django_session)
        statuses = {c["id"]: c["status"] for c in clips}
        pending = [cid for cid, s in statuses.items() if s not in ("complete", "error")]
        if not pending:
            return clips
        print(f"  Waiting... {len(pending)} clip(s) still processing: {pending}")
        time.sleep(interval)
    raise TimeoutError(f"Clips not complete after {timeout}s")


def main():
    clip_ids = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_CLIP_IDS

    print(f"Loading session from {SESSION_FILE}...")
    session = load_session()

    print("Refreshing JWT...")
    jwt = refresh_jwt(session)
    django_session = session["django_session_id"]
    print("  JWT refreshed.")

    print(f"Polling {len(clip_ids)} clip(s)...")
    clips = wait_for_completion(clip_ids, jwt, django_session)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for i, clip in enumerate(clips, start=1):
        clip_id = clip["id"]
        status = clip["status"]
        audio_url = clip.get("audio_url", "")
        title = clip.get("title", clip_id)

        if status == "error":
            print(f"  [{i}] SKIPPED (error): {clip_id}")
            continue

        if not audio_url:
            print(f"  [{i}] SKIPPED (no audio_url): {clip_id}")
            continue

        # Prefer .m4a (Opus ~143 kbps) over .mp3 (64 kbps) from the API audio_url.
        # The CDN hosts both at the same clip_id path — .m4a is what the web player uses.
        m4a_url = f"https://cdn1.suno.ai/{clip_id}.m4a"

        safe_title = sanitize_filename(title)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_{safe_title}__{clip_id[:8]}.m4a"
        dest = os.path.join(OUTPUT_DIR, filename)

        print(f"  [{i}] Downloading: {title}")
        print(f"       {m4a_url}")
        print(f"       -> {dest}")
        download_audio(m4a_url, dest)
        size_kb = os.path.getsize(dest) // 1024
        print(f"       Done ({size_kb} KB)")

    print("\nAll downloads complete.")


if __name__ == "__main__":
    main()
