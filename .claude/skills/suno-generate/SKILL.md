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
playwright-cli open --headed --persistent --profile=.refrakt/playwright-profile "https://suno.com/create"
```

**Important:** Always use `--headed --persistent --profile=.refrakt/playwright-profile`. The persistent profile avoids hCaptcha visual challenges. Without `--persistent`, hCaptcha will show image grids that block submission.

Wait a few seconds for the page to load.

### 3.2 — Inject Session Cookies

Read `.refrakt/suno_session.json` to get `client_token` and `django_session_id`, then set cookies:

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

#### a) Fill the form using `bin/suno-fill-form`

This helper reads `prompts_data.json` and fills Styles, Title, Lyrics, and Instrumental toggle in a single `playwright-cli run-code` call — avoiding shell escaping issues with multi-line lyrics:

```bash
bin/suno-fill-form --index 0              # fill first prompt (0-based)
bin/suno-fill-form --index 1              # fill second prompt
bin/suno-fill-form --dry-run              # preview without touching browser
```

The helper uses Playwright's native locator API (CSS selectors on placeholder text) rather than snapshot ref IDs, so it's resilient to ref rotation.

**If the prompt has an empty `prompt` field:** The lyricist agent and producer agent should have already populated the `prompt` and `tags` fields. If `prompt` is still empty, run the agents first before filling the form.

**If `suno-fill-form` fails** (e.g., can't find a field), fall back to manual filling:

1. Take a snapshot: `playwright-cli snapshot`
2. Find the element refs by searching the snapshot
3. Fill individually: `playwright-cli fill <ref> "<text>"`

For multi-line lyrics in the manual fallback, use `playwright-cli run-code`:
```bash
playwright-cli run-code "async page => { await page.locator('textarea[placeholder*=\"lyric\" i]').first().fill('your lyrics here'); }"
```

#### b) Click Create

```bash
playwright-cli click <create_ref>
```

Wait ~3 seconds, then take a snapshot to check for captcha.

#### c) Check for captcha

Search the post-click snapshot for any of these strings (case-insensitive):
- "Select everything"
- "hCaptcha"
- "Challenge Image"
- "Verify Answers"
- "captcha"
- "Please verify"

**If captcha detected:** Alert the user to solve it manually in the browser window. Take periodic snapshots to check if it clears. Once the captcha text disappears from the snapshot, continue.

**If no captcha:** Proceed. With `--persistent`, captcha should not appear.

#### d) Wait between submissions

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

Files are saved to `WIP_DIR/YYYY-MM-DD/` as `{Title}__{clip_id}.m4a` (Opus ~143kbps). After evaluation, the winner is promoted to `OUT_DIR`.

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
