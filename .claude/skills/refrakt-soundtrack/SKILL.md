---
name: refrakt-soundtrack
description: Create an original concept album soundtrack for a fictional movie. Designs story arc, generates all tracks via Suno, evaluates with Gemini, and packages for distribution.
---

# /refrakt-soundtrack — Create a Movie Soundtrack

End-to-end pipeline for creating an original concept album soundtrack.

## Arguments

- `--tracks <N>` — number of tracks (default: 16)
- `--name <album name>` — album title
- `--artist <artist name>` — artist name for metadata (default: "Refrakt")
- `--genre <base genre>` — the fusion genre base (e.g., "futuristic + blues + industrial rock")

---

## Phase 1 — Concept Design

### Story Arc
Work with the user to define:
1. **Movie concept** — genre, setting, protagonist, central conflict
2. **Story structure** — map tracks to narrative beats (Save the Cat, Hero's Journey, or custom)
3. **Sonic palette** — the base genre fusion that ties the album together
4. **Vocal tracks** — which beats get lyrics (typically: emotional nadir + credits)
5. **Tempo map** — each track's BPM matches its narrative energy

### Research the Sound
Use Perplexity to research the fusion genre palette:
```
"Describe the sonic palette of a film soundtrack that fuses [genre A], [genre B], and [genre C].
How would these genres blend? What specific instruments, production techniques, and textures
would define this fusion?"
```

### Create Tracklist
Save a `_tracklist.json` in the album's output folder with:
- Track number, beat name, concept, mood, tempo, genre weight, vocal flag
- `selected_clip: null` (user fills in after picking favorites)

This file is the source of truth — if tracks need regenerating, read intentions from here.

---

## Phase 2 — Build Prompts

For each track, create a `prompts_data.json` entry with:
- **tags**: Per-track tags mixing the album's genre base with track-specific mood/tempo
- **negative_tags**: `"vocals, singing, voice, spoken word"` for instrumentals; `"female vocals"` or `"male vocals"` for vocal tracks (opposite gender exclusion)
- **prompt**: Structural metatags for instrumentals (`[Intro]\n[Build]\n[Climax]\n[Outro]`); full lyrics for vocal tracks
- **invented_title**: Empty (agents will fill)
- **source_playlist**: Album name

### Write Lyrics for Vocal Tracks
Write lyrics that serve the story beat. The lyrics should:
- Be written from the protagonist's perspective
- Serve the narrative moment (e.g., despair, revelation, triumph)
- Use imagery consistent with the album's world
- Include Suno metatags: `[Verse]`, `[Chorus]`, `[Bridge]`, `[Outro]`, `[Fade To End]`

---

## Phase 3 — Title Generation

Spawn the song-title agent, then song-critic agent:
```
Task: "Read .claude/agents/song-title.md, then process prompts_data.json"
Task: "Read .claude/agents/song-critic.md, then process prompts_data.json"
```

For soundtracks, titles should feel cinematic (like Hans Zimmer, Trent Reznor, Vangelis cues), not pop songs.

---

## Phase 4 — Suno Submission

Follow the `/suno-generate` skill's Phase 3 (browser automation), with these soundtrack-specific notes:
- **Reload between every submission** — prevents stale form data
- Verify each title appears in the Suno feed after submission
- Submit all tracks, then batch poll + download

---

## Phase 5 — Evaluation

### Gemini Audio Eval
Run `lib/gemini_audio.py` on every clip:
```python
from lib.gemini_audio import evaluate_track
result = evaluate_track(audio_path, tags=tags, mood=mood, title=title, is_instrumental=True)
```

Flag tracks with `verdict: "Regenerate"` for re-submission.

### User Listening
Rename files to `##. Title (A).mp3` / `##. Title (B).mp3`. User listens, deletes rejects, removes suffix from keeper.

---

## Phase 6 — Packaging

### Metadata Tagging
For each final MP3:
- Title: track name
- Artist: album artist
- Album: album name
- Track number: N/total
- Genre: per-track genre description
- Year: current year
- Cover art: album-cover.jpeg embedded as APIC frame

### Full Album MP3
```bash
ffmpeg -f concat -safe 0 -i tracklist.txt -c copy "Album Name (Full Album).mp3"
```
Tag with album metadata + cover art.

### YouTube Video
Use `/youtube-upload` skill. **Remember: 16:9 widescreen cover image, NOT square.**

---

## Phase 7 — Iteration

If the user wants to regenerate specific tracks:
1. Read `_tracklist.json` for the original intentions
2. Rebuild just that track's prompt entry
3. Re-submit to Suno
4. Re-evaluate with Gemini
5. Replace the file in the album folder
6. Regenerate the full album MP3
