---
name: autonomous-album
description: Fully autonomous concept album creation — from finding a topic to publishing on YouTube. Finds a story in the news, designs a soundtrack, generates all music via Suno, creates album art via Gemini (Nano Banana), evaluates tracks with Gemini, and uploads to YouTube.
---

# /autonomous-album — Fully Autonomous Album Creation

Create an entire concept album from scratch — no human input needed after launch (except auth sessions).

## Arguments

- `--tracks <N>` — number of tracks (default: 12, range: 8-16)
- `--artist <name>` — artist name for metadata (default: "Denumerator")
- `--genre <hint>` — optional genre direction (e.g., "synthwave + jazz", "orchestral + metal"). If omitted, the AI chooses based on the story.
- `--vocal-tracks <N>` — number of tracks with vocals (default: 2)
- `--visibility <public|unlisted|private>` — YouTube visibility (default: unlisted)
- `--skip-youtube` — skip the YouTube upload step
- `--dry-run` — plan everything but don't submit to Suno or upload

---

## Timing

Track wall-clock time for each phase. At the start of the pipeline, note the current time. At the end of each phase, record elapsed time. Save all timings to `_timings.json` in the album folder:

```json
{
  "started_at": "2026-02-26T12:00:00",
  "phases": {
    "pre_flight": {"duration_sec": 15},
    "find_story": {"duration_sec": 180},
    "design_album": {"duration_sec": 300},
    "build_prompts": {"duration_sec": 120},
    "album_art": {"duration_sec": 45},
    "suno_submission": {"duration_sec": 240},
    "suno_polling": {"duration_sec": 600},
    "suno_download": {"duration_sec": 120},
    "gemini_eval": {"duration_sec": 180},
    "packaging": {"duration_sec": 90},
    "youtube_video": {"duration_sec": 60},
    "youtube_upload": {"duration_sec": 120},
    "retrospective": {"duration_sec": 180}
  },
  "total_sec": 2250,
  "total_human": "37 min 30 sec"
}
```

Use `date +%s` or Python `time.time()` to capture timestamps. Include these timings in both the final summary and the retrospective.

---

## Pre-Flight Checks

Before starting, verify all systems:

```bash
# 1. Check Suno credits
bin/suno credits
# Need: tracks × 10 credits (e.g., 12 tracks = 120 credits)

# 2. Verify Suno session
bin/suno auth

# 3. Test Gemini API
.venv/bin/python -c "from lib.gemini_audio import _load_api_key; print('Gemini OK:', bool(_load_api_key()))"

# 4. Verify Playwright persistent profile exists (for Gemini art + Suno submission)
ls .refrakt/playwright-profile/Default/Preferences > /dev/null && echo "Playwright profile OK"
```

If any check fails, alert the user and stop. Do NOT proceed with a partial pipeline.

---

## Phase 1 — Find a Story (3-5 minutes)

### Step 1.1: Discover a Topic
Use Perplexity MCP to find something compelling in the news:

```
"What are the most emotionally compelling, visually striking, or philosophically interesting
stories in the news right now? I'm looking for something that could inspire a concept album
soundtrack — it should have narrative arc potential (conflict, transformation, resolution).
Give me 5 options with a one-sentence pitch for each."
```

### Step 1.2: Pick the Best Story
Choose the story with the strongest narrative arc. Prefer stories that are:
- Emotionally resonant (not just factual)
- Visually cinematic (landscapes, conflict, transformation)
- Universal enough that the album stands alone without knowing the news source

### Step 1.3: Research the Story Deeply
Use Perplexity MCP to get details:

```
"Tell me the full story of [topic]. I need: the key characters, the timeline of events,
the emotional arc, the central conflict, and the resolution (or current state if ongoing).
What are the most vivid, visual moments? What emotions does each stage evoke?"
```

---

## Phase 2 — Design the Album (5-10 minutes)

### Step 2.1: Map Story to Save the Cat Beats

Create a beat sheet mapping the story to tracks. Use this template:

| # | Beat | Story Moment | Mood | Tempo | Vocal? |
|---|------|-------------|------|-------|--------|
| 1 | Opening Image | [scene] | [mood] | [BPM] | No |
| ... | ... | ... | ... | ... | ... |
| N-1 | Final Image | [scene] | [mood] | [BPM] | No |
| N | Credits | [abstract theme] | [mood] | [BPM] | Yes |

Rules for vocal track placement:
- One vocal track at the emotional nadir (typically "Dark Night of the Soul" or "All Is Lost")
- One vocal track for credits (last track — abstract, philosophical)
- Additional vocal tracks only if the story demands it

Rules for track count and variety:
- **12 tracks is the sweet spot** — 16 risks filler, 8 feels rushed. Every track should carry narrative weight.
- **Push for genre variation between tracks** — don't let the palette be too consistent. Action tracks should contrast strongly with intimate tracks.
- **Plan for ~30-40 min total** — Suno generates 2-4 min per track. Don't promise 60 min.

### Step 2.2: Choose a Sonic Palette

Use Perplexity MCP to research a genre fusion that matches the story's world:

```
"Describe the sonic palette of a film soundtrack that fuses [genre A], [genre B], and [genre C].
How would these genres blend? What instruments, production techniques, and textures define this?"
```

If `--genre` was provided, use that as the base. Otherwise, choose genres that match the story's setting and emotional register.

### Step 2.3: Write Lyrics for Vocal Tracks

Write lyrics from the protagonist's perspective at the relevant story moment:
- Use Suno metatags: `[Verse]`, `[Chorus]`, `[Bridge]`, `[Outro]`, `[Fade To End]`
- Keep under 200 words per song
- The credits track should be abstract/philosophical — hinting at the album's theme without being literal

### Step 2.4: Save the Tracklist

Save `_tracklist.json` in the album's output folder with full track intentions (beat, concept, mood, tempo, genre weight, vocal flag, lyrics if applicable). This is the re-generation reference.

---

## Phase 3 — Build Prompts (2-3 minutes)

### Step 3.1: Create `prompts_data.json`

For each track, build a prompt entry with:
- `source_track_name`: "Track N: Beat Name"
- `source_playlist`: Album name
- `tags`: Per-track tags (120-200 chars) blending the album's genre base with track-specific mood/tempo
- `negative_tags`: `"vocals, singing, voice, spoken word"` for instrumentals; opposite gender for vocals
- `prompt`: Structural metatags for instrumentals; full lyrics for vocal tracks
- `make_instrumental`: true/false
- `research`: Track concept + mood + genre weight (from tracklist)

### Step 3.2: Generate Titles

Spawn the title-designer agent:
```
Task: subagent_type="general-purpose", model="haiku"
Prompt: "Read .claude/agents/title-designer.md, then process prompts_data.json.
These are soundtrack cues — titles should be cinematic, not pop songs."
```

Then the title-critic agent:
```
Task: subagent_type="general-purpose", model="haiku"
Prompt: "Read .claude/agents/title-critic.md, then process prompts_data.json.
Soundtrack context — be demanding but recognize cinematic conventions."
```

If any titles are rejected, run title agent again with critic feedback, then re-evaluate. Max 2 rounds.

---

## Phase 4 — Generate Album Art (1-2 minutes)

### Step 4.1: Write Art Prompt

Based on the story and tracklist, write a detailed image generation prompt describing:
- The most iconic visual moment from the story
- Style, mood, color palette, composition
- "No text or lettering on the image" (text is added in step 4.3)

### Step 4.2: Generate Images via Gemini (Nano Banana)

Use Playwright to interact with Gemini's image generation:

1. Open Gemini in persistent browser: `playwright-cli open --headed --persistent --profile=.refrakt/playwright-profile "https://gemini.google.com"`
2. User selects "Thinking" model from dropdown
3. **Prefix ALL image prompts with "Generate an image:"** — without this prefix, the Thinking model analyzes/discusses rather than generating
4. Request **square 1:1** with title text included in the prompt
5. Wait ~60s for generation, download via "Download full size image" button
6. **Immediately move** downloaded file from `.refrakt/playwright-cli/` to SunoTemp with meaningful name — Playwright reuses filenames and will silently overwrite/cache
7. Ask Gemini to regenerate in **widescreen 16:9** aspect ratio with same composition
8. Download and move the widescreen version

**IMPORTANT:**
- Gemini images are ~2048-2752px. Never read them with Claude's Read tool (breaks context >2000px). Use accessibility snapshots only.
- After embedding cover art, **verify with hash comparison** that the correct image was used.

### Step 4.3: Add Title Text

Ask Gemini to add album title + artist name to both images:
- "ALBUM TITLE" in clean, modern, slightly futuristic sans-serif font, lower third
- "ARTIST NAME" in smaller text below
- Light/white with subtle glow effect for readability on dark backgrounds
- Download both titled versions

### Step 4.4: Save to Album Folder

Copy images from `.refrakt/playwright-cli/` to `output/ALBUM_NAME/`:
- `cover.png` — square with title (for MP3 metadata)
- `cover-wide.png` — widescreen with title (for YouTube video)

---

## Phase 5 — Submit to Suno (15-25 minutes)

### Step 5.1: Open Browser

```bash
playwright-cli open --headed --persistent --profile=.refrakt/playwright-profile "https://suno.com/create"
```

Inject session cookies from `.refrakt/suno_session.json`, reload.

### Step 5.2: Submit Each Track

For each track (index 0 through N-1):
```bash
playwright-cli reload          # CRITICAL: prevents stale form data
sleep 3
bin/suno-fill-form --index I
sleep 1
playwright-cli run-code "async page => { await page.getByRole('button', { name: 'Create song' }).click(); return 'ok'; }"
sleep 5
bin/suno feed | grep "TITLE"   # verify title appears
```

**If a title doesn't appear in the feed**, the submission failed. Retry that track (reload + fill + submit again).

### Step 5.3: Close Browser

```bash
playwright-cli close
```

### Step 5.4: Poll Until Complete

Get all clip IDs from the feed, then:
```bash
bin/suno poll <all_clip_ids> --wait
```

### Step 5.5: Download All Clips

```bash
bin/suno download <all_clip_ids>
```

---

## Phase 6 — Evaluate and Select (3-5 minutes)

### Step 6.1: Gemini Audio Evaluation

For each clip (2 per track), run:
```python
from lib.gemini_audio import evaluate_track
result = evaluate_track(audio_path, tags=tags, mood=mood, title=title, is_instrumental=is_inst)
```

### Step 6.2: Auto-Select Best Version

For each track, compare the two clips:
1. If one scores higher overall → pick it
2. If tied on overall score → pick the one with higher `artistic_interest`
3. If still tied → pick clip A (first generated)

### Step 6.3: Rename Files

Rename selected clips to `##. Title.mp3` in the album folder. Remove rejected clips.

### Step 6.4: Handle Regeneration

If any track gets `verdict: "Regenerate"` on BOTH clips:
1. Log the issue (which track, what the eval said)
2. Re-read `_tracklist.json` for the original intentions
3. Rebuild that track's prompt (possibly adjust tags based on Gemini's feedback)
4. Re-submit to Suno (open browser, submit just that track)
5. Re-evaluate
6. Max 3 attempts per track. After 3, pick the best of all attempts.

---

## Phase 7 — Package the Album (2-3 minutes)

### Step 7.1: Tag All Tracks

For each final MP3:
```python
from mutagen.id3 import ID3, TPE1, TPE2, TALB, TIT2, TRCK, TCON, APIC, TDRC
```
Set: title, artist, album artist, album, track number (N/total), genre, year, cover art (square PNG).

### Step 7.2: Sanitize Filenames

Before concatenation, sanitize all filenames:
- Replace curly apostrophes (`'`) with straight (`'`) — curly breaks ffmpeg concat paths
- Remove or replace any characters that cause shell/path issues

### Step 7.3: Create Full Album MP3

**IMPORTANT**: Use Python to build the concat list (handles special chars in paths) and copy files to a temp dir with simple numeric names to avoid ffmpeg path issues. Re-encode rather than copy to avoid duration header bugs:

```python
# Copy to temp dir with safe names, then:
ffmpeg -f concat -safe 0 -i concat.txt -c:a libmp3lame -b:a 320k "ALBUM (Full Album).mp3"
```

Do NOT use `-c copy` — variable-bitrate MP3 concat with copy produces wrong duration headers.

Tag the full album MP3 with metadata + cover art.

### Step 7.4: Generate Album Report

Save `_album_report.md` with:
- Album concept summary
- Track-by-track Gemini scores
- Which clip was selected for each track (A or B) and why
- Any tracks that needed regeneration
- Total cost (Suno credits + API costs)

---

## Phase 8 — Create YouTube Video (1-2 minutes)

### Step 8.1: Create MP4

**Use the widescreen image** (`album-cover-wide.png`), not the square:

```bash
ffmpeg -loop 1 -i "album-cover-wide.png" -i "ALBUM (Full Album).mp3" \
  -c:v libx264 -tune stillimage -c:a aac -b:a 320k \
  -pix_fmt yuv420p -shortest -y "ALBUM (Full Album).mp4"
```

### Step 8.2: Generate YouTube Description

Read each individual MP3's duration and build:
- Album title + artist
- Story concept (2-3 sentences)
- Tracklist with timestamps
- Genre, runtime, credits, hashtags

Save to `_youtube_description.txt`.

---

## Phase 9 — Upload to YouTube (2-3 minutes)

### Step 9.1: Open YouTube Studio

```bash
playwright-cli open --headed --persistent --profile=.refrakt/playwright-profile "https://studio.youtube.com"
```

If not logged in, alert user and wait. This is the ONE required human interaction.

### Step 9.2: Upload and Publish

Follow the `/youtube-upload` skill:
1. Create → Upload videos → set file input
2. Fill title: `"ALBUM NAME — Full Album | ARTIST (2026)"`
3. Fill description from `_youtube_description.txt`
4. Audience: "No, it's not made for kids"
5. Next × 3 → Visibility → set per `--visibility` arg
6. Publish/Save
7. Note the video URL

### Step 9.3: Close Browser

```bash
playwright-cli close
```

---

## Phase 10 — Write Retrospective

Create `docs/retrospectives/<album-name-kebab>.md` documenting:

1. **The inspiration** — what story/news was chosen and why
2. **The sonic palette** — what genre fusion was designed and how it worked
3. **The tracklist** — full table with titles, beats, and story moments
4. **Vocal tracks** — the lyrics and their significance
5. **Title generation** — notable titles and the critic's feedback
6. **Technical learnings** — what worked, what broke, what to do differently
7. **Album art** — the Gemini art prompt and the result

Include:
- Album cover image: convert to JPG, save to `docs/retrospectives/images/`, embed in markdown
- YouTube link
- Creation date and pipeline used
- **Phase-by-phase timing breakdown** from `_timings.json` — how long each step actually took, where bottlenecks were, comparison to estimates

This becomes a permanent record that visitors to the GitHub repo can read to understand how each album was made.

---

## Phase 11 — Final Summary

Print a summary to the user:

```
============================================================
  AUTONOMOUS ALBUM COMPLETE

  Album:    [name]
  Artist:   [artist]
  Tracks:   [N] ([N-vocal] vocal, [N-inst] instrumental)
  Runtime:  [MM:SS]

  Files:
    output/[album]/##. Track Name.mp3  (individual tracks)
    output/[album]/[album] (Full Album).mp3
    output/[album]/[album] (Full Album).mp4
    output/[album]/album-cover.png (square)
    output/[album]/album-cover-wide.png (widescreen)
    output/[album]/_tracklist.json
    output/[album]/_album_report.md
    output/[album]/_youtube_description.txt
    output/[album]/_timings.json

  YouTube:  [URL]

  Cost:
    Suno:   [N × 10] credits
    Gemini art: $0.00 (free via browser)
    Gemini: ~$[0.004 × N × 2] (audio eval)
    Total:  ~$[total]

  Timing:
    Story + design:    [X] min
    Suno gen + poll:   [X] min
    Gemini eval:       [X] min
    Packaging + upload:[X] min
    Total:             [X] min
============================================================
```

---

## Error Handling

- **Suno session expired**: Print "Suno session expired. Please re-authenticate and restart." Stop.
- **YouTube not logged in**: Print "Please log into YouTube in the browser window." Wait for user confirmation.
- **Gemini rate limit**: Wait 60 seconds, retry. Max 3 retries.
- **Gemini image generation failure**: Rephrase prompt, retry. If Gemini browser session expired, ask user to re-navigate. Max 3 retries.
- **Suno generates vocals on instrumental track**: Flag in report, suggest regeneration with stronger negative tags.
- **All clips for a track score < 3**: Regenerate with adjusted tags. Max 3 attempts.

---

## Timing Estimate

| Phase | Time |
|-------|------|
| 1. Find story | 3-5 min |
| 2. Design album | 5-10 min |
| 3. Build prompts | 2-3 min |
| 4. Album art | 1-2 min |
| 5. Suno submission + poll | 15-25 min |
| 6. Evaluate + select | 3-5 min |
| 7. Package | 2-3 min |
| 8. YouTube video | 1-2 min |
| 9. YouTube upload | 2-3 min |
| **Total** | **35-60 min** |
