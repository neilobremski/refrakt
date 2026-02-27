#!/usr/bin/env python3
"""
rf.py — Unified pipeline orchestrator for Refrakt.

Coordinates existing tools (bin/refrakt, bin/suno, bin/prompts, agents) into a
single pipeline with state tracking and resume support. Does not reimplement
anything — calls existing scripts via subprocess.

Usage (via bin/rf):
    rf run --playlist "NeilPop" --track "Song for Zula"
    rf run --playlist "NeilPop" --random
    rf run --resume
    rf run --from tags --until submit
    rf run --only eval
    rf status
    rf list --playlist "NeilPop" [--not-generated] [--search "zula"]
    rf credits
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
PROMPTS_FILE = BASE_DIR / "prompts_data.json"
TRACKING_FILE = BASE_DIR / "generated_tracks.json"
PLAYLIST_CACHE_FILE = BASE_DIR / ".refrakt" / "caches" / "playlist.json"

WIP_DIR = Path(os.path.expanduser(os.getenv("WIP_DIR", "~/Google Drive/My Drive/SunoTemp/")))
OUT_DIR = Path(os.path.expanduser(os.getenv("OUT_DIR", "~/Downloads")))

# Stage names in execution order
STAGE_NAMES = [
    "select",
    "lyrics",
    "lyrics-review",
    "tags",
    "title",
    "art",
    "submit",
    "pick",
    "tag",
    "check",
]

# Stages that require Claude to spawn agents (not auto-executable)
AGENT_STAGES = {"lyrics", "lyrics-review", "tags", "title", "art"}

# Stages that auto-execute via subprocess
CLI_STAGES = {"select", "submit", "pick", "tag", "check"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_prompts():
    if not PROMPTS_FILE.exists():
        return []
    with open(PROMPTS_FILE) as f:
        return json.load(f)


def save_prompts(prompts):
    import tempfile
    fd, tmp_path = tempfile.mkstemp(
        dir=PROMPTS_FILE.parent, suffix=".tmp", prefix=".prompts_"
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(prompts, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp_path, PROMPTS_FILE)
    except Exception:
        os.unlink(tmp_path)
        raise


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_pipeline(entry):
    return entry.get("_pipeline", {})


def set_pipeline(entry, pipeline):
    entry["_pipeline"] = pipeline


def mark_stage(entry, stage, status, extra=None):
    """Update pipeline state for a stage. Saves to prompts_data.json."""
    pipeline = get_pipeline(entry)
    pipeline[stage] = {"status": status, "at": now_iso()}
    if extra:
        pipeline[stage].update(extra)
    set_pipeline(entry, pipeline)

    prompts = load_prompts()
    if not prompts:
        print("WARNING: prompts_data.json is empty; stage state not persisted", file=sys.stderr)
        return
    prompts[0] = entry
    save_prompts(prompts)


def run_bin(script, *args, check=True):
    """Run a bin/ script, returning CompletedProcess."""
    cmd = [sys.executable, str(BASE_DIR / "bin" / script)] + list(args)
    return subprocess.run(cmd, cwd=str(BASE_DIR), check=check)


def sanitize_filename(name):
    import re
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    return name.strip().replace(" ", "_")


def fmt_duration(seconds):
    if seconds < 60:
        return f"{seconds:.0f}s"
    m, s = divmod(int(seconds), 60)
    return f"{m}m{s:02d}s"


def agent_stage_completed(name, entry):
    """Check if an agent stage's work is already reflected in prompts_data.json.

    When --resume runs, agent stages stuck in 'running' get checked here.
    If the agent's output is present, we auto-advance to 'done'.
    """
    if name == "lyrics":
        return bool(entry.get("prompt", "").strip())
    elif name == "lyrics-review":
        # If lyrics exist and no _lyrics_rejected field, critic approved
        return bool(entry.get("prompt", "").strip()) and "_lyrics_rejected" not in entry
    elif name == "tags":
        return bool(entry.get("tags", "").strip())
    elif name == "title":
        # Title-designer replaces the auto-generated title; check for temp fields
        title = entry.get("invented_title", "")
        return bool(title) and "_title_candidates" not in entry and "_title_rejected" not in entry
    elif name == "art":
        # Check for cover art files in WIP
        import glob as _glob
        title = entry.get("invented_title", "")
        safe_title = sanitize_filename(title) if title else ""
        if not safe_title:
            return False
        art_patterns = [
            str(WIP_DIR / "**" / f"*cover*{safe_title}*"),
            str(WIP_DIR / "**" / "*cover*"),
        ]
        for p in art_patterns:
            matches = [f for f in _glob.glob(p, recursive=True)
                       if f.endswith((".png", ".jpg", ".jpeg"))]
            if matches:
                return True
        return False
    return False


# ---------------------------------------------------------------------------
# Stage icons and formatting
# ---------------------------------------------------------------------------

def stage_icon(status):
    icons = {
        "done": "\u2713",
        "running": "\u25b6",
        "failed": "\u2717",
        "skip": "\u2500",
        "pending": "\u00b7",
    }
    return icons.get(status, "?")


def print_stage(name, status, detail=""):
    icon = stage_icon(status)
    status_str = status.ljust(7)
    detail_str = f" \u2014 {detail}" if detail else ""
    print(f"  {icon} {name:<14} {status_str}{detail_str}")


def print_agent_instruction(stage, agent_file, prompt_text):
    """Print instructions for Claude to spawn an agent."""
    print(f"\n  \u2192 AGENT: Spawn {stage} agent (Haiku)")
    print(f"    Agent file: .claude/agents/{agent_file}")
    print(f"    Prompt: \"{prompt_text}\"")
    print(f"    Resume: rf run --resume   (after agent completes)")


# ---------------------------------------------------------------------------
# Stage runners
# ---------------------------------------------------------------------------

def run_select(entry, args):
    """Stage 1: Pick track, fetch lyrics, research, write prompts_data.json."""
    cmd_args = ["--playlist", args.playlist]
    if args.track:
        cmd_args += ["--track", args.track]
    elif args.random:
        cmd_args += ["--random"]
    elif args.index is not None:
        cmd_args += ["--index", str(args.index)]
    else:
        cmd_args += ["--random"]

    if args.seed is not None:
        cmd_args += ["--seed", str(args.seed)]

    result = run_bin("refrakt", *cmd_args)
    if result.returncode != 0:
        raise RuntimeError(f"bin/refrakt exited with code {result.returncode}")

    # Reload entry after refrakt wrote it
    prompts = load_prompts()
    if not prompts:
        raise RuntimeError("prompts_data.json is empty after select")
    entry.update(prompts[0])

    title = entry.get("invented_title", "?")
    source = entry.get("source_track_name", "?")
    return f"{source} \u2192 {title}"


def run_lyrics(entry, args):
    """Stage 2: Spawn lyricist agent."""
    print_agent_instruction(
        "lyrics",
        "lyricist.md",
        "Read .claude/agents/lyricist.md for instructions, then process prompts_data.json",
    )
    return "awaiting agent"


def run_lyrics_review(entry, args):
    """Stage 3: Spawn lyrics-critic agent."""
    print_agent_instruction(
        "lyrics-review",
        "lyrics-critic.md",
        "Read .claude/agents/lyrics-critic.md for instructions, then process prompts_data.json",
    )
    return "awaiting agent"


def run_tags(entry, args):
    """Stage 4: Spawn producer agent."""
    print_agent_instruction(
        "tags",
        "producer.md",
        "Read .claude/agents/producer.md for instructions, then process prompts_data.json",
    )
    return "awaiting agent"


def run_title(entry, args):
    """Stage 5: Spawn title-designer + title-critic agents."""
    print_agent_instruction(
        "title",
        "title-designer.md",
        "Read .claude/agents/title-designer.md for instructions, then process prompts_data.json",
    )
    print(f"\n    Then spawn title-critic:")
    print(f"    Agent file: .claude/agents/title-critic.md")
    print(f'    Prompt: "Read .claude/agents/title-critic.md for instructions, then process prompts_data.json"')
    return "awaiting agent"


def run_art(entry, args):
    """Stage 6: Spawn artist agent (can run in background)."""
    print_agent_instruction(
        "art",
        "artist.md",
        "Read .claude/agents/artist.md for instructions. Generate album art for the track at index 0.",
    )
    print(f"    Tip: spawn with run_in_background=true")
    return "awaiting agent"


def run_submit(entry, args):
    """Stage 7: Submit to Suno via browser automation."""
    result = run_bin("suno", "submit", "--index", "0", check=False)
    if result.returncode != 0:
        raise RuntimeError(f"bin/suno submit exited with code {result.returncode}")

    # Count WIP candidates
    import glob as _glob
    title = entry.get("invented_title", "")
    safe_title = sanitize_filename(title)
    wip_pattern = str(WIP_DIR / "**" / f"*{safe_title}__*.m4a")
    candidates = _glob.glob(wip_pattern, recursive=True)
    return f"{len(candidates)} clips"


def run_pick(entry, args):
    """Stage 8: Gemini eval, copy winner to OUT_DIR."""
    result = run_bin("suno", "pick", "--index", "0", check=False)
    if result.returncode != 0:
        raise RuntimeError(f"bin/suno pick exited with code {result.returncode}")

    # Check for winner in OUT_DIR
    title = entry.get("invented_title", "")
    import glob as _glob
    out_pattern = str(OUT_DIR / "**" / f"*{title}*.m4a")
    out_files = _glob.glob(out_pattern, recursive=True)
    if out_files:
        return f"winner copied to OUT_DIR"
    return "completed"


def run_tag(entry, args):
    """Stage 9: Embed cover art into winner M4A."""
    title = entry.get("invented_title", "")
    safe_title = sanitize_filename(title)

    # Find cover art in WIP — check track-specific art dir first, then broader patterns
    import glob as _glob
    art_patterns = [
        # Track-specific art directory (preferred — most precise)
        str(WIP_DIR / "**" / f"{safe_title}_art" / "cover.png"),
        str(WIP_DIR / "**" / f"{safe_title}_art" / "cover.*"),
        # Title-specific cover files
        str(WIP_DIR / "**" / f"*cover*{safe_title}*"),
        # Generic cover files in the same date dir (last resort)
        str(WIP_DIR / "**" / f"{safe_title} - cover.*"),
    ]
    art_files = []
    for p in art_patterns:
        matches = [f for f in _glob.glob(p, recursive=True)
                   if f.endswith((".png", ".jpg", ".jpeg"))]
        if matches:
            art_files = matches
            break  # Use the most specific match found

    if not art_files:
        raise RuntimeError(
            f"No cover art found for '{title}' in WIP_DIR. "
            f"Expected: {WIP_DIR}/**/{safe_title}_art/cover.png"
        )

    # Find winner M4A in OUT_DIR
    out_pattern = str(OUT_DIR / "**" / f"*{title}*.m4a")
    out_files = _glob.glob(out_pattern, recursive=True)
    if not out_files:
        raise RuntimeError(f"No output M4A found for '{title}' in OUT_DIR")

    # Embed cover art
    cover_path = art_files[0]
    m4a_path = out_files[0]

    try:
        from mutagen.mp4 import MP4, MP4Cover

        with open(cover_path, "rb") as f:
            cover_data = f.read()

        # Embed in M4A
        m4a = MP4(m4a_path)
        if m4a.tags is None:
            m4a.add_tags()
        img_fmt = MP4Cover.FORMAT_PNG if cover_path.endswith(".png") else MP4Cover.FORMAT_JPEG
        m4a.tags["covr"] = [MP4Cover(cover_data, imageformat=img_fmt)]
        m4a.save()

        # Also embed in companion MP3 if it exists
        mp3_path = m4a_path.replace(".m4a", ".mp3")
        if os.path.exists(mp3_path):
            from mutagen.mp3 import MP3
            from mutagen.id3 import APIC
            mp3 = MP3(mp3_path)
            if mp3.tags is None:
                mp3.add_tags()
            # Remove any existing APIC frames (e.g. from download-time tagging)
            for key in [k for k in mp3.tags.keys() if k.startswith("APIC")]:
                del mp3.tags[key]
            mime = "image/png" if cover_path.endswith(".png") else "image/jpeg"
            mp3.tags.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=cover_data))
            mp3.save()

        return f"cover embedded from {Path(cover_path).name}"
    except ImportError:
        raise RuntimeError("mutagen not installed. Run: pip install mutagen")
    except Exception as e:
        raise RuntimeError(f"Failed to embed cover: {e}")


def run_check(entry, args):
    """Stage 10: Validate all completion criteria."""
    result = run_bin("refrakt", "check", "--index", "0", check=False)
    if result.returncode != 0:
        raise RuntimeError("Completion check failed (some steps incomplete)")
    return "ALL CLEAR"


# Stage function mapping
STAGE_FUNCS = {
    "select": run_select,
    "lyrics": run_lyrics,
    "lyrics-review": run_lyrics_review,
    "tags": run_tags,
    "title": run_title,
    "art": run_art,
    "submit": run_submit,
    "pick": run_pick,
    "tag": run_tag,
    "check": run_check,
}


# ---------------------------------------------------------------------------
# Pipeline control
# ---------------------------------------------------------------------------

def should_skip(name, pipeline, entry, args):
    """Determine if a stage should be skipped."""
    # --only: skip everything except the named stage
    if args.only and name != args.only:
        return True

    # --from: skip stages before the start point
    if args.from_stage:
        from_idx = STAGE_NAMES.index(args.from_stage)
        curr_idx = STAGE_NAMES.index(name)
        if curr_idx < from_idx:
            return True

    # --until: skip stages after the end point
    if args.until:
        until_idx = STAGE_NAMES.index(args.until)
        curr_idx = STAGE_NAMES.index(name)
        if curr_idx > until_idx:
            return True

    # --resume: skip stages already done, or auto-advance agent stages
    if args.resume:
        stage_info = pipeline.get(name, {})
        if stage_info.get("status") == "done":
            return True
        # Auto-advance: if an agent stage is "running" but its work is
        # already reflected in the data, mark it done and skip
        if stage_info.get("status") == "running" and name in AGENT_STAGES:
            if agent_stage_completed(name, entry):
                mark_stage(entry, name, "done", {"auto_advanced": True})
                return True

    return False


def cmd_run(args):
    """Execute the pipeline."""
    # Validate stage names in --from/--until/--only
    for flag, val in [("--from", args.from_stage), ("--until", args.until), ("--only", args.only)]:
        if val and val not in STAGE_NAMES:
            print(f"ERROR: {flag} '{val}' is not a valid stage", file=sys.stderr)
            print(f"Valid stages: {', '.join(STAGE_NAMES)}", file=sys.stderr)
            sys.exit(1)

    # Resume mode: load existing entry
    if args.resume:
        prompts = load_prompts()
        if not prompts:
            print("ERROR: No prompts_data.json to resume from", file=sys.stderr)
            sys.exit(1)
        entry = prompts[0]
    else:
        # Need playlist for select stage
        if not args.playlist:
            print("ERROR: --playlist is required (or use --resume)", file=sys.stderr)
            sys.exit(1)
        entry = {}

    pipeline = get_pipeline(entry)

    # Print header
    title = entry.get("invented_title", "(pending)")
    source = entry.get("source_track_name", "")
    source_artists = ", ".join(entry.get("source_artists", []))
    if source:
        header = f"Pipeline: {title} (from: {source} \u2014 {source_artists})"
    else:
        playlist = args.playlist or "?"
        track_desc = args.track or ("random" if args.random else "?")
        header = f"Pipeline: {playlist} / {track_desc}"
    print(f"\n{header}")
    print(f"\u2500" * min(len(header), 70))

    if args.dry_run:
        print("  [DRY RUN \u2014 no actions will be taken]\n")

    # Execute stages
    for name in STAGE_NAMES:
        if should_skip(name, pipeline, entry, args):
            stage_info = pipeline.get(name, {})
            if stage_info.get("status") == "done":
                detail = _summarize_done_stage(name, entry, stage_info)
                print_stage(name, "done", detail)
            else:
                print_stage(name, "skip")
            continue

        if args.dry_run:
            if name in AGENT_STAGES:
                print_stage(name, "pending", f"would spawn agent")
            else:
                print_stage(name, "pending", f"would execute")
            continue

        # Execute the stage
        t0 = time.time()
        fn = STAGE_FUNCS[name]

        # Agent stages: mark as running, print instructions, and pause
        if name in AGENT_STAGES:
            mark_stage(entry, name, "running")
            print_stage(name, "running", "")
            try:
                result = fn(entry, args)
            except Exception as e:
                mark_stage(entry, name, "failed", {"error": str(e)})
                print_stage(name, "failed", str(e))
                sys.exit(1)

            # Agent stages pause here — Claude will spawn the agent
            # and then resume with `rf run --resume`
            elapsed = time.time() - t0
            print(f"\n  Pipeline paused. Run 'rf run --resume' after agent completes.")
            sys.exit(0)

        # CLI stages: auto-execute
        mark_stage(entry, name, "running")
        print_stage(name, "running", "")
        try:
            result = fn(entry, args)
            elapsed = time.time() - t0
            mark_stage(entry, name, "done", {"elapsed": round(elapsed, 1)})

            # Reload entry in case the stage modified prompts_data.json
            prompts = load_prompts()
            if prompts:
                entry = prompts[0]

            print_stage(name, "done", f"({fmt_duration(elapsed)}) {result or ''}")
        except Exception as e:
            elapsed = time.time() - t0
            mark_stage(entry, name, "failed", {"error": str(e), "elapsed": round(elapsed, 1)})
            print_stage(name, "failed", str(e))
            if not args.continue_on_error:
                print(f"\n  Pipeline stopped. Fix the issue and run 'rf run --resume'.")
                sys.exit(1)

    # All stages complete
    title = entry.get("invented_title", "?")
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\nPipeline complete. Output: {OUT_DIR}/{today}/{title}.*")


def _summarize_done_stage(name, entry, stage_info):
    """Generate a short summary for a completed stage."""
    elapsed = stage_info.get("elapsed")
    elapsed_str = f"({fmt_duration(elapsed)}) " if elapsed else ""

    if name == "select":
        source = entry.get("source_track_name", "?")
        return f"{elapsed_str}{source}"
    elif name == "lyrics":
        prompt_len = len(entry.get("prompt", ""))
        return f"{elapsed_str}{prompt_len} chars"
    elif name == "lyrics-review":
        return f"{elapsed_str}approved"
    elif name == "tags":
        tags_len = len(entry.get("tags", ""))
        return f"{elapsed_str}{tags_len} chars"
    elif name == "title":
        title = entry.get("invented_title", "?")
        return f'{elapsed_str}"{title}"'
    elif name == "art":
        return f"{elapsed_str}cover art generated"
    elif name == "submit":
        clip_ids = stage_info.get("clip_ids", [])
        return f"{elapsed_str}{len(clip_ids)} clips" if clip_ids else f"{elapsed_str}submitted"
    elif name == "pick":
        winner = stage_info.get("winner", "")
        score = stage_info.get("score", "")
        parts = [elapsed_str]
        if winner:
            parts.append(winner[:8])
        if score:
            parts.append(f"({score}/5)")
        return " ".join(parts).strip()
    elif name == "tag":
        return f"{elapsed_str}cover embedded"
    elif name == "check":
        return f"{elapsed_str}ALL CLEAR"
    return elapsed_str.strip("() ")


# ---------------------------------------------------------------------------
# rf status
# ---------------------------------------------------------------------------

def cmd_status(args):
    """Show current pipeline state."""
    prompts = load_prompts()
    if not prompts:
        print("No active pipeline. Run 'rf run --playlist ... --track ...' to start.")
        return

    entry = prompts[0]
    pipeline = get_pipeline(entry)
    title = entry.get("invented_title", "(untitled)")
    source = entry.get("source_track_name", "?")
    source_artists = ", ".join(entry.get("source_artists", []))

    print(f"\nPipeline: {title} (from: {source} \u2014 {source_artists})")
    print("\u2500" * 66)

    for name in STAGE_NAMES:
        stage_info = pipeline.get(name, {})
        status = stage_info.get("status", "pending")
        detail = _summarize_done_stage(name, entry, stage_info)
        print_stage(name, status, detail)

    # Summary
    done_count = sum(1 for n in STAGE_NAMES if pipeline.get(n, {}).get("status") == "done")
    total = len(STAGE_NAMES)
    print(f"\n  Progress: {done_count}/{total} stages complete")

    if done_count == total:
        today = datetime.now().strftime("%Y-%m-%d")
        print(f"  Output: {OUT_DIR}/{today}/{title}.*")
    else:
        # Find next stage
        for name in STAGE_NAMES:
            status = pipeline.get(name, {}).get("status", "pending")
            if status != "done":
                if status == "running":
                    print(f"  Current: {name} (in progress)")
                else:
                    print(f"  Next: {name}")
                break


# ---------------------------------------------------------------------------
# rf list
# ---------------------------------------------------------------------------

def cmd_list(args):
    """List tracks from a playlist, optionally filtering out already-generated ones."""
    if not args.playlist:
        print("ERROR: --playlist is required", file=sys.stderr)
        sys.exit(1)

    # Load from playlist cache
    if not PLAYLIST_CACHE_FILE.exists():
        print(f"ERROR: No cached playlists. Run 'bin/refrakt --playlist \"{args.playlist}\" --list --random' first.", file=sys.stderr)
        sys.exit(1)

    with open(PLAYLIST_CACHE_FILE) as f:
        cache = json.load(f)

    key = args.playlist.lower()
    if key not in cache:
        # Try to fetch it via refrakt
        print(f"Playlist '{args.playlist}' not in cache. Fetching...")
        result = run_bin("refrakt", "--playlist", args.playlist, "--list", "--random", check=False)
        # Reload cache
        if PLAYLIST_CACHE_FILE.exists():
            with open(PLAYLIST_CACHE_FILE) as f:
                cache = json.load(f)
        if key not in cache:
            print(f"ERROR: Could not load playlist '{args.playlist}'", file=sys.stderr)
            sys.exit(1)

    tracks = cache[key]["tracks"]
    total = len(tracks)

    # Load generated track IDs
    generated_ids = set()
    if TRACKING_FILE.exists():
        try:
            with open(TRACKING_FILE) as f:
                tracking = json.load(f)
            generated_ids = set(tracking.get("track_ids", []))
        except (json.JSONDecodeError, OSError):
            pass

    # Filter
    if args.not_generated:
        tracks = [t for t in tracks if t["id"] not in generated_ids]

    if args.search:
        search = args.search.lower()
        tracks = [t for t in tracks
                  if search in t["name"].lower()
                  or any(search in a.lower() for a in t["artists"])]

    # Display
    gen_count = sum(1 for t in cache[key]["tracks"] if t["id"] in generated_ids)
    print(f"\n{args.playlist}: {total} tracks ({gen_count} generated, {total - gen_count} remaining)")
    print(f"\u2500" * 70)

    if not tracks:
        if args.not_generated:
            print("  All tracks have been generated!")
        elif args.search:
            print(f"  No tracks matching '{args.search}'")
        return

    print(f"{'#':<5} {'Track':<35} {'Artist':<25} {'Dur':<6} Gen")
    print(f"{'─'*5} {'─'*35} {'─'*25} {'─'*6} {'─'*3}")

    for i, t in enumerate(tracks):
        name = t["name"][:34]
        artist = ", ".join(t["artists"])[:24]
        dur = t["duration_ms"] // 1000
        dur_str = f"{dur//60}:{dur%60:02d}"
        gen = "\u2713" if t["id"] in generated_ids else ""
        # Find original index in full list
        orig_idx = next((j for j, ft in enumerate(cache[key]["tracks"]) if ft["id"] == t["id"]), i)
        print(f"{orig_idx+1:<5} {name:<35} {artist:<25} {dur_str:<6} {gen}")

    shown = len(tracks)
    if args.not_generated:
        print(f"\n  Showing {shown} ungenerated tracks")
    elif args.search:
        print(f"\n  Showing {shown} matching tracks")


# ---------------------------------------------------------------------------
# rf credits
# ---------------------------------------------------------------------------

def cmd_credits(args):
    """Show Suno credits remaining."""
    run_bin("suno", "credits")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="rf",
        description="Refrakt pipeline orchestrator — coordinates agents and tools.",
    )
    sub = parser.add_subparsers(dest="command")

    # rf run
    p_run = sub.add_parser("run", help="Execute the pipeline (full or partial)")
    p_run.add_argument("--playlist", type=str, help="Spotify playlist name")
    p_run.add_argument("--track", type=str, help="Track name to search for")
    p_run.add_argument("--random", action="store_true", help="Pick a random track")
    p_run.add_argument("--index", type=int, default=None, help="Track index (1-based)")
    p_run.add_argument("--seed", type=int, default=None, help="Random seed")
    p_run.add_argument("--resume", action="store_true", help="Resume from last incomplete stage")
    p_run.add_argument("--from", dest="from_stage", type=str, default=None,
                        metavar="STAGE", help="Start from this stage")
    p_run.add_argument("--until", type=str, default=None,
                        metavar="STAGE", help="Stop after this stage")
    p_run.add_argument("--only", type=str, default=None,
                        metavar="STAGE", help="Run only this stage")
    p_run.add_argument("--dry-run", action="store_true", help="Show what would happen")
    p_run.add_argument("--continue-on-error", action="store_true",
                        help="Continue to next stage even if one fails")
    p_run.set_defaults(func=cmd_run)

    # rf status
    p_status = sub.add_parser("status", help="Show current pipeline state")
    p_status.set_defaults(func=cmd_status)

    # rf list
    p_list = sub.add_parser("list", help="List tracks from a playlist")
    p_list.add_argument("--playlist", type=str, help="Spotify playlist name")
    p_list.add_argument("--not-generated", action="store_true",
                         help="Only show tracks not yet processed")
    p_list.add_argument("--search", type=str, default=None,
                         help="Filter by track/artist name")
    p_list.set_defaults(func=cmd_list)

    # rf credits
    p_credits = sub.add_parser("credits", help="Show Suno credits remaining")
    p_credits.set_defaults(func=cmd_credits)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
