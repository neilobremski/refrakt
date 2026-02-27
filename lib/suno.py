#!/usr/bin/env python3
"""
suno.py — Swiss army knife CLI for the Refrakt pipeline.

Auth is read from .refrakt/suno_session.json (gitignored).

Usage:
    .venv/bin/python suno.py <command> [args...]

Commands:
    auth                  Verify session and print user/credit info
    credits               Show remaining credits
    feed [--page N]       List recent clips (default page 0)
    poll <clip_id> ...    Poll clip status until complete (or show current status)
    download <clip_id>... Download completed clips to output/ (.m4a, Opus ~143kbps)
    session-save          Re-extract session tokens from the Playwright browser
                          (requires a logged-in headed session)

Audio note:
    The API returns audio_url pointing to .mp3 (64 kbps).
    The web player uses .m4a (Opus ~143 kbps) — same CDN path, much better quality.
    All download commands use .m4a by default.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_BASE_DIR = Path(__file__).parent.parent
SESSION_FILE = str(_BASE_DIR / ".refrakt" / "suno_session.json")
OUTPUT_DIR = str(_BASE_DIR / "output")
AUTH_BASE = "https://auth.suno.com"
API_BASE = "https://studio-api.prod.suno.com"
CDN_BASE = "https://cdn1.suno.ai"


# ---------------------------------------------------------------------------
# Session / Auth
# ---------------------------------------------------------------------------

def load_session() -> dict:
    if not os.path.exists(SESSION_FILE):
        sys.exit(f"ERROR: {SESSION_FILE} not found. Log into Suno via the browser first.")
    with open(SESSION_FILE) as f:
        return json.load(f)


def refresh_jwt(session: dict) -> str:
    """Exchange the long-lived __client token for a fresh short-lived JWT (~60s TTL)."""
    r = requests.post(
        f"{AUTH_BASE}/v1/client/sessions/{session['session_id']}/tokens",
        headers={
            "Cookie": f"__client={session['client_token']}",
            "Origin": "https://suno.com",
        },
        params={"_clerk_js_version": "5.36.2"},
    )
    r.raise_for_status()
    return r.json()["jwt"]


def get_auth_headers(session: dict, jwt: str) -> dict:
    return {
        "Authorization": f"Bearer {jwt}",
        "Cookie": f"sessionid={session['django_session_id']}",
    }


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------

def get_session_info(session: dict, jwt: str) -> dict:
    """Fetch /api/session/ — user info, subscription, credits."""
    r = requests.get(
        f"{API_BASE}/api/session/",
        headers=get_auth_headers(session, jwt),
    )
    r.raise_for_status()
    return r.json()


def get_billing_info(session: dict, jwt: str) -> dict:
    """Fetch /api/billing/info/ — credit balance."""
    r = requests.get(
        f"{API_BASE}/api/billing/info/",
        headers=get_auth_headers(session, jwt),
    )
    r.raise_for_status()
    return r.json()


def get_feed(session: dict, jwt: str, page: int = 0) -> list:
    """Fetch the user's clip feed."""
    r = requests.get(
        f"{API_BASE}/api/feed/",
        headers=get_auth_headers(session, jwt),
        params={"page": page},
    )
    r.raise_for_status()
    return r.json()


def poll_clips(session: dict, jwt: str, clip_ids: list) -> list:
    """Fetch status of specific clip IDs."""
    ids_param = ",".join(clip_ids)
    r = requests.get(
        f"{API_BASE}/api/feed/?ids={ids_param}",
        headers=get_auth_headers(session, jwt),
    )
    r.raise_for_status()
    return r.json()


def wait_for_completion(session: dict, jwt: str, clip_ids: list,
                        timeout: int = 300, interval: int = 5) -> list:
    """Poll until all clips are complete or errored."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        clips = poll_clips(session, jwt, clip_ids)
        pending = [c["id"] for c in clips if c["status"] not in ("complete", "error")]
        if not pending:
            return clips
        print(f"  [{int(deadline - time.time())}s left] Waiting: {len(pending)} clip(s) still processing...")
        time.sleep(interval)
    raise TimeoutError(f"Clips not complete after {timeout}s")


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    return name.strip().replace(" ", "_")


def transcode_to_mp3(m4a_path: str, bitrate: str = "320k") -> str | None:
    """Transcode .m4a (Opus) to .mp3 for Apple Music compatibility. Returns mp3 path or None."""
    if not shutil.which("ffmpeg"):
        return None
    mp3_path = str(Path(m4a_path).with_suffix(".mp3"))
    try:
        result = subprocess.run(
            ["ffmpeg", "-i", m4a_path, "-c:a", "libmp3lame", "-b:a", bitrate,
             "-map_metadata", "0", "-id3v2_version", "3", "-y", mp3_path],
            capture_output=True, text=True, timeout=60,
        )
        if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0:
            return mp3_path
        print(f"  WARNING: ffmpeg exited {result.returncode}: {result.stderr[:200]}", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print(f"  WARNING: ffmpeg transcode timed out for {m4a_path}", file=sys.stderr)
    except OSError as e:
        print(f"  WARNING: ffmpeg transcode failed: {e}", file=sys.stderr)
    return None


def download_file(url: str, dest_path: str) -> int:
    """Stream-download url to dest_path. Returns file size in bytes."""
    r = requests.get(url, stream=True)
    r.raise_for_status()
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
    with open(dest_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=65536):
            f.write(chunk)
    return os.path.getsize(dest_path)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_auth(args):
    """Verify auth and show user/credit summary."""
    session = load_session()
    print("Refreshing JWT...")
    jwt = refresh_jwt(session)
    print("  OK — JWT refreshed.\n")

    info = get_session_info(session, jwt)
    print(f"User:         {info.get('display_name', '?')} (@{info.get('handle', '?')})")
    print(f"User ID:      {info.get('id', '?')}")

    sub = info.get("subscription_type") or info.get("role")
    if sub:
        print(f"Subscription: {sub}")

    try:
        billing = get_billing_info(session, jwt)
        credits_left = billing.get("total_credits_left") or billing.get("credits_left")
        if credits_left is not None:
            print(f"Credits:      {credits_left}")
        else:
            print(f"Billing raw:  {json.dumps(billing, indent=2)}")
    except Exception as e:
        print(f"(Could not fetch billing: {e})")


def cmd_credits(args):
    """Show remaining credits."""
    session = load_session()
    jwt = refresh_jwt(session)
    billing = get_billing_info(session, jwt)
    credits_left = billing.get("total_credits_left") or billing.get("credits_left")
    if credits_left is not None:
        print(f"Credits remaining: {credits_left}")
    else:
        print(json.dumps(billing, indent=2))


def cmd_feed(args):
    """List recent clips from the user's feed."""
    session = load_session()
    jwt = refresh_jwt(session)
    page = getattr(args, "page", 0)
    clips = get_feed(session, jwt, page=page)
    if not clips:
        print("(No clips found)")
        return
    print(f"{'ID':36}  {'Status':12}  {'Title'}")
    print("-" * 80)
    for clip in clips:
        clip_id = clip.get("id", "?")
        status = clip.get("status", "?")
        title = clip.get("title", "")
        print(f"{clip_id}  {status:12}  {title}")


def cmd_poll(args):
    """Poll clip status. Waits until complete if --wait is set."""
    session = load_session()
    jwt = refresh_jwt(session)
    clip_ids = args.clip_ids

    if getattr(args, "wait", False):
        print(f"Polling {len(clip_ids)} clip(s) until complete...")
        clips = wait_for_completion(session, jwt, clip_ids)
    else:
        clips = poll_clips(session, jwt, clip_ids)

    for clip in clips:
        clip_id = clip.get("id", "?")
        status = clip.get("status", "?")
        title = clip.get("title", "")
        audio_url = clip.get("audio_url", "")
        print(f"\n{clip_id}")
        print(f"  Status:  {status}")
        print(f"  Title:   {title}")
        if audio_url:
            m4a_url = f"{CDN_BASE}/{clip_id}.m4a"
            print(f"  MP3 URL: {audio_url}")
            print(f"  M4A URL: {m4a_url}  (Opus ~143kbps — preferred)")


def cmd_download(args):
    """Download completed clips to output/ as .m4a (Opus ~143kbps) + .mp3 (320kbps) for Apple Music."""
    session = load_session()
    jwt = refresh_jwt(session)
    clip_ids = args.clip_ids

    print(f"Polling {len(clip_ids)} clip(s)...")
    clips = wait_for_completion(session, jwt, clip_ids)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load prompts for album name metadata (matched per-clip by title)
    prompts = []
    try:
        with open(str(_BASE_DIR / "prompts_data.json")) as f:
            prompts = json.load(f)
        if not isinstance(prompts, list):
            prompts = []
    except (OSError, json.JSONDecodeError):
        pass

    for i, clip in enumerate(clips, start=1):
        clip_id = clip["id"]
        status = clip["status"]
        title = clip.get("title", clip_id)
        audio_url = clip.get("audio_url", "")

        if status == "error":
            print(f"  [{i}] SKIPPED (error): {clip_id}")
            continue
        if not audio_url:
            print(f"  [{i}] SKIPPED (no audio_url yet): {clip_id}")
            continue

        # Use .m4a (Opus ~143kbps) rather than .mp3 (64kbps) from audio_url
        m4a_url = f"{CDN_BASE}/{clip_id}.m4a"
        safe_title = sanitize_filename(title)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_{safe_title}__{clip_id[:8]}.m4a"
        dest = os.path.join(OUTPUT_DIR, filename)

        print(f"  [{i}] {title}")
        print(f"       {m4a_url}")
        print(f"       -> {dest}")
        size = download_file(m4a_url, dest)
        print(f"       Done ({size // 1024} KB)")

        # Tag with metadata (match clip to prompt by title for album name)
        try:
            from tag_tracks import tag_file, match_prompt_to_clip
            prompt_entry = match_prompt_to_clip(clip, prompts) if prompts else None
            tag_file(dest, clip, prompt=prompt_entry)
            print(f"       Tagged with metadata.")
        except Exception as e:
            print(f"       WARNING: Could not tag: {e}")

        # Transcode to MP3 for Apple Music compatibility
        mp3_path = transcode_to_mp3(dest)
        if mp3_path:
            print(f"       Transcoded to MP3 ({os.path.getsize(mp3_path) // 1024} KB)")
        else:
            print(f"       WARNING: Could not transcode to MP3 (ffmpeg missing or failed)")

    print("\nAll downloads complete.")


# ---------------------------------------------------------------------------
# Main / argparse
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=".venv/bin/python suno.py",
        description="Swiss army knife CLI for the Refrakt Suno AI pipeline.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # auth
    p_auth = sub.add_parser("auth", help="Verify session and show user/credit info")
    p_auth.set_defaults(func=cmd_auth)

    # credits
    p_credits = sub.add_parser("credits", help="Show remaining credits")
    p_credits.set_defaults(func=cmd_credits)

    # feed
    p_feed = sub.add_parser("feed", help="List recent clips from your feed")
    p_feed.add_argument("--page", type=int, default=0, help="Page number (default 0)")
    p_feed.set_defaults(func=cmd_feed)

    # poll
    p_poll = sub.add_parser("poll", help="Poll clip status")
    p_poll.add_argument("clip_ids", nargs="+", metavar="clip_id")
    p_poll.add_argument("--wait", action="store_true",
                        help="Keep polling until all clips are complete")
    p_poll.set_defaults(func=cmd_poll)

    # download
    p_dl = sub.add_parser("download", help="Download completed clips as .m4a (Opus ~143kbps)")
    p_dl.add_argument("clip_ids", nargs="+", metavar="clip_id")
    p_dl.set_defaults(func=cmd_download)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
