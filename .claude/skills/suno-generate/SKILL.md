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

After running `bin/refrakt`, spawn the Refrakt agent (Haiku model) to write refracted lyrics from the original:

```
Task tool: subagent_type="general-purpose", model="haiku"
Prompt: "Read .claude/agents/refrakt.md for instructions, then process prompts_data.json"
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

## Phase 3 — Browser Automation (Interactive)

This is the core interactive phase. You will control the browser step-by-step using `playwright-cli` commands via the Bash tool.

### 3.1 — Open Browser

```bash
playwright-cli open --headed --persistent --profile=.playwright-profile "https://suno.com/create"
```

**Important:** Always use `--headed --persistent --profile=.playwright-profile`. The persistent profile avoids hCaptcha visual challenges. Without `--persistent`, hCaptcha will show image grids that block submission.

Wait a few seconds for the page to load.

### 3.2 — Inject Session Cookies

Read `.suno_session.json` to get `client_token` and `django_session_id`, then set cookies:

```bash
playwright-cli cookie-set __client "<client_token>" --domain=.suno.com --path=/ --secure --httpOnly
playwright-cli cookie-set sessionid "<django_session_id>" --domain=.suno.com --path=/ --secure --httpOnly
```

Then reload to apply:

```bash
playwright-cli reload
```

Wait a few seconds for the page to reload with the authenticated session.

### 3.3 — Switch to Custom Mode

Suno always opens in **Simple** mode by default. You must switch to Custom mode to access the Styles, Lyrics, and Title fields.

Take a snapshot and look for the mode toggle buttons:

```bash
playwright-cli snapshot
```

The snapshot returns a YAML-like accessibility tree. Each interactive element has a `[ref=XXXX]` identifier. Find the "Custom" button and click it:

```bash
playwright-cli click <custom_ref>
```

**Typical snapshot pattern for the mode toggle:**
```
- button "Simple" [ref=eXXX]
- button "Custom" [ref=eYYY] [cursor=pointer]
```

After clicking Custom, take another snapshot to confirm the form now shows Lyrics, Styles, and Title fields.

**How to find elements:** Search the snapshot text for keywords. Elements look like:
```
- button "Custom" [ref=e42]
- textbox "Write some lyrics..." [ref=e138]
- textbox "darker, cry, slow buildup..." [ref=e205]
- textbox "Song Title (Optional)" [ref=e300]
- button "Create song" [ref=e400]
```

The ref values change every snapshot. Always take a fresh snapshot before looking for refs.

### 3.4 — For Each Prompt: Fill and Submit

For each prompt from `prompts_data.json`:

#### a) Take a fresh snapshot

```bash
playwright-cli snapshot
```

#### b) Identify the form elements

Search the snapshot for these elements:

| Element | What to look for | Notes |
|---------|-----------------|-------|
| **Styles textbox** | A textbox near a "Styles" heading. May have placeholder text like "power chords, gritty flow..." or "Describe the style of music..." | Usually the first/larger textbox |
| **Title textbox** | A textbox with "Song Title" or "Title" placeholder | Usually a smaller textbox below Styles |
| **Lyrics textbox** | A textbox with placeholder "Write some lyrics or a prompt — or leave blank for instrumental" | The large text area for lyrics/prompts |
| **Instrumental toggle** | A button, switch, or checkbox labeled "Instrumental" | Should be enabled; check if already toggled on |
| **Create button** | A button labeled "Create" or "Create song" | The submit button |

**Search strategy:** Look for these patterns (case-insensitive) in snapshot lines:
- Styles: `textbox` near text containing "style", "tag", "power chords", "gritty", "synth", "describe"
- Title: `textbox` near "title" or "song title"
- Lyrics: `textbox` near "lyrics" or "prompt" or "write some lyrics"
- Instrumental: `button`/`switch`/`checkbox` near "instrumental"
- Create: `button` with text "Create"

If a UI element isn't found, take a screenshot for debugging:
```bash
playwright-cli screenshot
```
Then read the screenshot image to visually identify the layout.

#### c) Fill the Styles field

```bash
playwright-cli fill <styles_ref> "<tags from prompt>"
```

#### d) Fill the Title field

```bash
playwright-cli fill <title_ref> "<invented_title from prompt>"
```

#### e) Fill the Lyrics field

**If the prompt has a non-empty `prompt` field:** Fill the Lyrics textbox directly with its contents (structural metatags for instrumentals, or pre-written lyrics).

**If the prompt has an empty `prompt` field and an `original_lyrics` field:** The prompt is for a vocal track that needs new lyrics written. Use the `original_lyrics` (fetched from Genius) and `research` (from Perplexity) as inspiration to write **completely new, original lyrics** that:
- Follow a similar thematic arc, mood, and emotional trajectory as the original
- Use fresh imagery and different words — NOT a copy or close paraphrase
- Preserve the structural feel (verse/chorus/bridge pattern) but with new content
- Use Suno metatags: `[Verse 1]`, `[Chorus]`, `[Verse 2]`, `[Bridge]`, `[Chorus]`, `[Outro]`
- Keep to ~200 words of lyrics
- Match the sonic character described in the `tags` field

Then fill the Lyrics textbox with the newly generated lyrics.

**If `original_lyrics` is empty** (instrumental or not on Genius), generate lyrics from the `research` field's thematic description instead.

```bash
playwright-cli fill <lyrics_ref> "<lyrics content>"
```

#### f) Set Instrumental toggle

Check the prompt's `make_instrumental` field. Take a fresh snapshot to check the Instrumental toggle state. Look for "pressed", "checked", or similar indicators.

- If `make_instrumental` is `true` and toggle is **off** → click to enable
- If `make_instrumental` is `false` and toggle is **on** → click to disable
- If already in the correct state → do nothing

```bash
playwright-cli click <instrumental_ref>
```

#### g) Click Create

```bash
playwright-cli click <create_ref>
```

Wait ~3 seconds, then take a snapshot to check for captcha.

#### h) Check for captcha

Search the post-click snapshot for any of these strings (case-insensitive):
- "Select everything"
- "hCaptcha"
- "Challenge Image"
- "Verify Answers"
- "captcha"
- "Please verify"

**If captcha detected:** Alert the user to solve it manually in the browser window. Take periodic snapshots to check if it clears. Once the captcha text disappears from the snapshot, continue.

**If no captcha:** Proceed. With `--persistent`, captcha should not appear.

#### i) Wait between submissions

Wait ~12 seconds before the next prompt to let the generation queue settle.

### 3.5 — Close Browser

After all prompts are submitted:

```bash
playwright-cli close
```

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

Files are saved to `output/` as `YYYYMMDDhhmmss_{title}__{clip_id}.m4a` (Opus ~143kbps).

---

## Phase 6 — Update Tracking

Update `generated_tracks.json` to mark source tracks as generated. The file format is `{"track_ids": [...]}` — a JSON object with a `track_ids` array of Spotify track IDs.

Read the current file (or create `{"track_ids": []}` if it doesn't exist), append the `source_track_id` from each successfully submitted prompt, and write it back:

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

## Troubleshooting

### "Could not find element"
The UI structure may have changed. Take a screenshot (`playwright-cli screenshot`) and read it visually. Adapt your search patterns to match the current layout.

### Captcha appears despite `--persistent`
The persistent profile may have been cleared. Try:
1. Complete the captcha manually in the browser
2. Continue with the remaining prompts
3. Future sessions should auto-pass again

### Session expired
If you get auth errors after cookie injection, the session tokens in `.suno_session.json` may be stale. The user will need to update them.

### Form fields don't clear
If `fill` doesn't replace existing text, try clicking the field first (`click <ref>`), selecting all (`press Control+a`), then typing:
```bash
playwright-cli click <ref>
playwright-cli press Control+a
playwright-cli type "<new text>"
```

---

## Prerequisites

- `.suno_session.json` with valid `client_token` and `django_session_id`
- `playlist_data.json` enriched with genres (run `/enrich` first)
- `playwright-cli` installed and in PATH
- `bin/` scripts on PATH (handled by SessionStart hook)
