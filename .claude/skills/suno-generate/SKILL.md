---
name: suno-generate
description: End-to-end Suno generation pipeline — interactive browser workflow
allowed-tools: Bash(playwright-cli *), Bash(bin/generate-prompts *), Bash(bin/refrakt *), Bash(bin/suno *), Bash(bin/download-tracks *), Bash(.venv/bin/python *)
user-invocable: true
argument-hint: "[--count N] [--seed SEED] [--no-download]"
---

# /suno-generate — Interactive Suno Generation

End-to-end pipeline: generate prompts, open a browser, interactively fill the Suno custom-mode form, submit each prompt, poll for completion, and download results.

**This is an interactive knowledge skill.** Claude navigates the browser by reading snapshots and making decisions dynamically — not by running a single script.

## Arguments

Parse these from the user's invocation:

- `--count N` — number of songs to generate (default: 2)
- `--seed SEED` — random seed for reproducible prompt selection (optional)
- `--no-download` — skip downloading after generation

---

## Phase 1 — Generate Prompts

**For instrumental tracks** (from Wordless Work playlist):

```bash
bin/generate-prompts --count N [--seed SEED]
```

**For Refrakt vocal tracks** (from any playlist):

```bash
bin/refrakt --playlist "Playlist Name" --track "Track Name"
bin/refrakt --playlist "Playlist Name" --random
bin/refrakt --playlist "Playlist Name" --index 5
```

Use `--list` to browse tracks: `bin/refrakt --playlist "Name" --list --random`

After running `bin/refrakt`, spawn the lyricist agent (Haiku model) to write refracted lyrics from the original:

```
Task tool: subagent_type="general-purpose", model="haiku"
Prompt: "Read .claude/agents/lyricist.md for instructions, then process prompts_data.json"
```

After the lyricist agent writes refracted lyrics, spawn the producer agent to optimize tags with vocal descriptors:

```
Task tool: subagent_type="general-purpose", model="haiku"
Prompt: "Read .claude/agents/producer.md for instructions, then process prompts_data.json"
```

This reads the research field (which now includes vocal character description) and the vocal prompting guide to generate optimized style tags with explicit vocal descriptors (gender, tone, texture) placed early for maximum weight.

After tags are generated, spawn the title-designer agent to replace the auto-generated title with a creative one:

```
Task tool: subagent_type="general-purpose", model="haiku"
Prompt: "Read .claude/agents/title-designer.md for instructions, then process prompts_data.json"
```

This mines the refracted lyrics (for vocals) or research (for instrumentals) to find the most evocative image or phrase, and writes a compelling title that varies in structure (1-5 words, not always two abstract words).

After the title-designer, spawn the title-critic agent to evaluate candidates:

```
Task tool: subagent_type="general-purpose", model="haiku"
Prompt: "Read .claude/agents/title-critic.md for instructions, then process prompts_data.json"
```

If the critic rejects, run the title-designer again with the feedback, then re-evaluate. Max 2 rejection rounds.

**Spawn album art in background** — while waiting for title approval or later steps, spawn the artist agent to generate cover art (runs in parallel):

```
Task tool: subagent_type="general-purpose", model="haiku", run_in_background=true
Prompt: "Read .claude/agents/artist.md for instructions. Generate album art for the track."
```

This writes `prompts_data.json`. Read that file to get the list of prompts. Each entry has:
- `source_track_id` — Spotify track ID (for tracking)
- `source_track_name` — original track name (for reference only, never sent to Suno)
- `invented_title` — the title to use in Suno's form
- `tags` — rich descriptive style tags for the Styles field (Perplexity-researched)
- `negative_tags` — tags to avoid (e.g., "vocals, singing, voice, spoken word" for instrumentals; empty for vocal tracks)
- `prompt` — structural metatags for the Lyrics field (instrumentals), or empty if lyrics need generation (vocal tracks)
- `original_lyrics` — (vocal tracks only) original lyrics from Genius, used as inspiration for writing new lyrics
- `make_instrumental` — `true` for instrumentals, `false` for vocal tracks
- `research` — raw Perplexity research text (for reference and lyric generation context)

---

## Phase 2 — Snapshot Feed (Before)

Capture the current Suno feed so we can diff later to discover new clips:

```bash
bin/suno feed
```

Note the clip IDs that already exist. Save them for comparison in Phase 4.

---

## Phase 3 — Submit to Suno

Use `bin/suno submit` which handles the entire browser automation in one command:
- Opens browser with persistent profile (captcha-free)
- Injects session cookies
- Creates 3 tag variations (vocal-led, genre-led, texture-led)
- Fills form and clicks Create for each variation
- Closes browser and discovers new clip IDs via feed diffing

```bash
bin/suno submit --index 0                 # submit with 3 variations, poll + download
bin/suno submit --index 0 --no-download   # submit only, download later
bin/suno submit --index 0 --variations 1  # single variation (10 credits instead of 30)
```

The command outputs new clip IDs when complete. If `--no-download` is not set, it automatically polls and downloads all clips.

**If `bin/suno submit` fails** (e.g., captcha appears, session expired), fall back to manual browser orchestration. See `.claude/agents/suno.md` for the step-by-step approach with `playwright-cli`.

---

## Phase 4 — Discover New Clips

Run the feed again and compare against the Phase 2 snapshot:

```bash
bin/suno feed
```

Identify new clip IDs that weren't in the Phase 2 output. These are the clips just generated.

If no new clips appear, wait a few seconds and try again — there may be a brief delay before they show up in the feed.

---

## Phase 5 — Poll and Download

### Poll for completion

For each new clip ID, poll until status is `complete`:

```bash
bin/suno poll <clip_id_1> <clip_id_2> ... --wait
```

This blocks until all clips finish (status: `complete`) or times out.

### Download

Unless `--no-download` was specified:

```bash
bin/suno download <clip_id_1> <clip_id_2> ...
```

Or use the standalone downloader:

```bash
bin/download-tracks <clip_id_1> <clip_id_2> ...
```

Files are saved to `WIP_DIR/YYYY-MM-DD/` as `{Title}__{clip_id}.m4a` (Opus ~143kbps). After evaluation, the winner is promoted to `OUT_DIR`.

---

## Phase 6 — Album Art + Tracking

### 6.1 — Album Art

If the artist agent was spawned in the background during Phase 1, check that it completed and generated cover art. If not, spawn it now:

```
Task tool: subagent_type="general-purpose", model="haiku"
Prompt: "Read .claude/agents/artist.md for instructions. Generate album art for the track at index 0."
```

The artist agent generates square (1:1) for M4A metadata and widescreen (16:9) for YouTube, then embeds the square cover into the output M4A file.

### 6.2 — Update Tracking

Update `generated_tracks.json` to mark source tracks as generated:

```python
.venv/bin/python -c "
import json
try:
    with open('generated_tracks.json') as f: data = json.load(f)
    ids = set(data['track_ids'])
except FileNotFoundError: ids = set()
ids |= {'<track_id_1>', '<track_id_2>'}
with open('generated_tracks.json', 'w') as f: json.dump({'track_ids': sorted(ids)}, f, indent=2)
"
```

Replace the track IDs with the actual `source_track_id` values from the submitted prompts.

---

## Phase 7 — Validate Completion

Run `bin/refrakt-check` to verify all pipeline steps completed:

```bash
bin/refrakt-check --index 0
```

This checks 8 steps: tags, lyrics, title, WIP candidates (6), output winner, cover art embedded, album art files, tracking updated. Any `✗` means a step was missed — fix it before declaring done.

---

## Troubleshooting

### "Could not find element"
The UI structure may have changed. Take a screenshot (`playwright-cli screenshot`) and read it visually. Adapt your search patterns to match the current layout.

### Captcha appears despite `--persistent`
The persistent profile may have been cleared. Try:
1. Complete the captcha manually in the browser
2. Continue with the remaining prompts
3. Future sessions should auto-pass again

### Session expired
If you get auth errors after cookie injection, the session tokens in `.refrakt/suno_session.json` may be stale. The user will need to update them.

### Form fields don't clear
If `fill` doesn't replace existing text, try clicking the field first (`click <ref>`), selecting all (`press Control+a`), then typing:
```bash
playwright-cli click <ref>
playwright-cli press Control+a
playwright-cli type "<new text>"
```

### Suno React form — element identification notes
Suno uses React components, not raw HTML `<input>`/`<textarea>` elements. Key findings:
- **`getAttribute('placeholder')` returns null** on these components. Don't use CSS selectors like `textarea[placeholder*="style"]` — they won't match.
- **Use `getByRole('textbox', { name: /pattern/ })`** which reads the accessible name from the accessibility tree (same names shown in `playwright-cli snapshot`).
- **`fill()` works** for Lyrics and Title fields when called via `getByRole` locators, even with multi-line content.
- **The Styles textbox has rotating placeholder text** (e.g., "smooth transitions, wistful...", "power chords, gritty flow...", "gothic symphonic metal..."). Match it by exclusion: find all textboxes, skip lyrics/title/search/enhance/workspace.
- **`insertText()` works for Styles** when `fill()` doesn't trigger React state — use click + Cmd+A + Backspace + insertText.
- **`keyboard.type()` is too slow** for lyrics (types character by character). Use `fill()` or `insertText()` instead.

---

## Prerequisites

- `.refrakt/suno_session.json` with valid `client_token` and `django_session_id`
- `playlist_data.json` enriched with genres (run `/enrich` first)
- `playwright-cli` installed and in PATH
- `bin/` scripts on PATH (handled by SessionStart hook)
