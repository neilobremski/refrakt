# CLAUDE.md — Project Context for Claude Code

## Project Goal

Build an end-to-end pipeline:

1. Read the Spotify playlist **"Wordless Work"** (private playlist belonging to the user)
2. Analyze each track's audio features, genres, and overall vibe
3. Generate a Suno AI style prompt per track — with an **invented title** (not derived from the original track name, to avoid guard rails)
4. Submit each prompt to Suno AI, wait for generation to complete
5. Download the resulting MP3s to `output/`
6. (Later) Tag the MP3s with ID3 metadata (title, album art, etc.)

The playlist is instrumental/ambient. The aim is to create original Suno-generated instrumentals that capture a similar mood and musical character to the source tracks.

---

## Current State (as of Feb 25 2026)

### Completed
- Spotify Developer App created (credentials in `.env`)
- `fetch_playlist.py` working — fetched 1341 tracks from "Wordless Work"
  - Output: `playlist_data.json` (gitignored)
  - Uses `/items` endpoint (newer; `/tracks` is deprecated and 403s)
- `enrich_genres.py` working — enriches tracks with Last.fm genre tags
  - Queries `artist.getTopTags` for each unique artist, caches to `.refrakt/caches/lastfm.json`
  - Filters out non-genre tags (personal tags, ratings, years)
  - Updates `playlist_data.json` in-place with `genres` field per track
- Suno session authentication confirmed working
  - Session stored in `.refrakt/suno_session.json` (gitignored)
  - JWT refresh via Clerk confirmed working
- First test generation completed: 2 clips generated, downloaded to `output/`
  - Note: test clips used the original track name ("Semi Detached") — future generations must use invented titles per the title convention below
- `suno.py` — CLI for auth verification, credit check, feed listing, polling, and downloading
- `download_tracks.py` working (standalone download utility)
- Both download tools prefer `.m4a` (Opus ~143 kbps) over `.mp3` (64 kbps) from the API
- Post-download transcode: `ffmpeg` converts `.m4a` (Opus) to `.mp3` (320 kbps) for Apple Music compatibility
  - Apple Music silently rejects Opus-in-M4A containers — the MP3 copy ensures importability
  - Both files kept: `.m4a` for archival quality, `.mp3` for Apple Music import
- `bin/suno-generate` — full end-to-end loop: prompt generation → browser automation → polling → download
  - Uses `playwright-cli --headed --persistent` for captcha-free submission
  - Discovers new clips via feed diffing (before/after snapshot)
  - Downloads with timestamp prefix: `YYYYMMDDhhmmss_{title}__{clip_id}.m4a`
- Project reorganized: CLI entry points in `bin/`, `.py` modules in root as importable libraries
- Skills restructured to `SKILL.md` frontmatter pattern under `.claude/skills/{name}/SKILL.md`
- M4A metadata tagging: `bin/suno-tag` writes title, artist, album, genre, year, comment, description, and cover art
  - Auto-tags on download via `bin/suno download`; retro-tag with `bin/suno-tag --all`
- Per-track Perplexity AI research for prompt generation
  - `lib/perplexity.py` — REST API client for Perplexity (sonar-pro model)
  - Phase 1: Research each track's musical character via Perplexity (cached to `.refrakt/caches/prompt_research.json`)
  - Phase 2: Synthesize research into rich descriptive Suno tags (120-200 chars with sonic textures, mood, BPM)
  - Structural metatags in Lyrics field (`[Intro]\n[Slow Build]\n...`) based on genre/duration
  - Negative tags always set to `"vocals, singing, voice, spoken word"` for instrumental tracks
  - API key stored in `.env` as `PERPLEXITY_API_KEY`
  - **Important:** When Claude is making Perplexity queries directly (not via pipeline scripts), always use the MCP tool rather than curl or calling `lib/perplexity.py`. Pipeline scripts like `bin/generate-prompts` and `bin/refrakt` use the Python library internally — that's fine.
- **Refrakt** — original songs refracted from existing ones
  - `lib/refrakt.py` + `bin/refrakt` — pick a track from any playlist, fetch original lyrics from Genius, research via Perplexity, synthesize tags
  - `lib/genius.py` — fetches original lyrics from Genius (free API, token in `.env` as `GENIUS_ACCESS_TOKEN`)
  - `.claude/agents/lyricist.md` — Haiku-powered agent that writes refracted lyrics (same spirit, completely new words)
  - Pipeline: `bin/refrakt` → spawn lyricist agent → `/suno-generate`
  - Artist name: read from `ARTIST_NAME` in `.env` (default: "Refrakt" if not set). Neil's is "Denumerator".
  - First refraction: "Glass Cradle" (refracted from "Retrovertigo" by Mr. Bungle, Rocket playlist)

- Vocal character capture in Perplexity research
  - `research_track()` query now explicitly asks for singer's gender, range, tone, delivery, and distinctive traits
  - Tags left empty by `bin/refrakt` — delegated to producer agent for richer vocal-aware generation
- `docs/suno-vocal-prompting.md` — Suno vocal prompting research guide
  - Vocal descriptor taxonomy (gender, range, texture, delivery, emotional quality)
  - Tag placement strategy (Style Tags for global voice, Lyrics metatags for section changes)
  - Negative tags for gender control, reliable community-tested combos, known limitations
- `.claude/agents/producer.md` — Haiku agent for tag generation with vocal character
  - Reads research + vocal prompting guide → writes optimized `tags` and `negative_tags`
  - Vocal descriptors placed early in tag string for higher Suno weight
  - Pipeline: `bin/refrakt` → lyricist agent (lyrics) → producer agent (tags) → title-designer agent (title) → `/suno-generate`
- `.claude/agents/title-designer.md` — Haiku agent for creative song title generation
  - Mines refracted lyrics or research for the most evocative image/phrase
  - Replaces generic auto-generated titles with specific, intriguing names
  - Varies structure: 1-5 words, not always two abstract words
- `bin/suno-fill-form` — form fill helper for Suno browser automation
  - Reads `prompts_data.json`, fills Styles/Title/Lyrics/Instrumental via `playwright-cli run-code`
  - Uses `getByRole('textbox', {name: /pattern/})` — Suno's React components don't have HTML placeholder attributes, so CSS selectors fail. Role-based selectors read from the accessibility tree.
  - Styles field identified by exclusion (rotating placeholder text doesn't match any fixed pattern)
  - `fill()` works for Lyrics/Title; Styles needs `click + Cmd+A + Backspace + insertText` for React state
  - Bypasses shell escaping issues with multi-line lyrics — `json.dumps()` embeds content as JS string literals
  - Claude still handles browser open/cookies/mode switch/captcha/create click interactively

- `.claude/agents/title-critic.md` — Haiku agent for adversarial title evaluation
  - Evaluates title candidates against quality heuristics (image test, surprise test, sonic test, genre fit)
  - Uses WebSearch for uniqueness checks (is this already a famous song?)
  - Approves or rejects with specific feedback; max 2 rejection rounds
  - Sequential pattern: title-designer agent → title-critic agent → (repeat if rejected)
- `.claude/agents/audio-critic.md` — Haiku agent for ruthless audio quality evaluation
  - Combines Gemini 2.5 Flash listening with librosa signal analysis
  - Detects: truncation, generic loops, batch similarity, low variety, vocal mismatch
  - Extra strict on instrumental electronic tracks (the biggest quality risk)
  - Uses `lib/audio_analysis.py` for quantitative metrics
- `.claude/agents/story-designer.md` — Haiku agent for narrative arc design
  - 6 frameworks: Save the Cat, Hero's Journey, 90-Day Novel, Story Circle, archetypes, three-act
  - Designs protagonist with dilemma (not just plot), maps beats to tracks
- `.claude/agents/code-reviewer.md` — Sonnet agent for code review before pushing
  - Reviews for security (credential exposure, shell injection), bugs, code quality, style
  - Spawned before every `git push`; fix issues and re-run until CLEAR TO PUSH
- `lib/gemini_audio.py` — Gemini 2.5 Flash audio evaluation for AI-powered music listening
  - Uploads generated tracks to Gemini, gets structured JSON evaluation
  - Checks: vocal contamination, genre match, mood match, production quality, artistic interest
  - Verdict: Keep / Marginal / Regenerate with 1-5 scores
  - Cost: ~$0.004/track; API key in `.env` as `GEMINI_API_KEY`
  - Use `evaluate_track(audio_path, tags, mood, title, is_instrumental)` from Python
- **Soundtrack creation** — original concept album workflow
  - Define movie concept + story arc (Save the Cat / Hero's Journey beat mapping)
  - 12-16 tracks with per-beat mood/tempo/genre tags, 1-2 vocal tracks
  - Save tracklist intentions to `_tracklist.json` for re-generation reference
  - Full pipeline: research palette → build prompts → title/critic agents → submit → Gemini eval → user picks A/B → tag → concat → YouTube
  - First soundtrack: "Alive Through the Rift" by Denumerator (16 tracks, futuristic blues + industrial rock)
- `lib/dalle_art.py` — DALL-E 3 album art generation (legacy, replaced by Gemini)
  - Generates square (1024x1024) for MP3 metadata and widescreen (1792x1024) for YouTube
  - API key in `.env` as `OPENAI_API_KEY`
- **Album art via Gemini (Nano Banana)** — preferred method
  - Generate via Playwright browser automation at gemini.google.com (Thinking model)
  - Widescreen 16:9 for YouTube, square 1:1 for MP3 metadata
  - Add album title + artist name as text on the image (Gemini handles text well)
  - Free (no API cost), higher quality than DALL-E, supports iterative refinement
  - **Never read Gemini images with Claude's Read tool** — they're >2000px and break context
- `/autonomous-album` skill — fully autonomous concept album creation
  - From news topic to YouTube in ~45 minutes with zero human input (except auth)
  - Pipeline: Perplexity → story → beats → prompts → Gemini art → Suno → Gemini eval → auto-select → tag → concat → YouTube
- **YouTube upload** workflow via Playwright browser automation
  - Create video from album: `ffmpeg -loop 1 -i cover.jpeg -i album.mp3 -c:v libx264 -tune stillimage -c:a aac -b:a 320k -pix_fmt yuv420p -shortest output.mp4`
  - **Use 16:9 widescreen image (1920x1080) for YouTube** — square album art crops badly
  - Generate tracklist with timestamps from individual MP3 durations
  - Upload via youtube.com/studio: Create → Upload → fill title/description → set audience → Publish
  - Persistent Playwright profile handles Google auth

### In Progress / Next Steps
- (none currently)

### Generation Strategy
- **3 prompt variations per song** — vary the first tag (position 1 carries ~50% weight), BPM, and structural metatags to force sonic diversity
- Each variation generates 2 clips → **6 candidates total per song**
- Audio-critic evaluates all 6 → auto-picks the best → copies to `output/YYYY-MM-DD/`
- Cost: 30 credits per song (3 generations × 10 credits). Quality over quantity.
- If all 6 candidates REJECT, auto-regen with adjusted tags (max 2 regen rounds)

### Scale Planning
- 1341 tracks at 30 credits per generation = 40,230 credits total
- Pro tier provides 2,500 credits/month (~83 songs)
- Full playlist would take ~16 months at Pro tier, or work in prioritized batches

---

## Spotify Setup

### Redirect URI
Registered URI: `http://127.0.0.1:8888/callback`

- Spotify's auth server rejects `https://localhost`
- Spotify's dashboard blocks `http://localhost`
- `http://127.0.0.1` is accepted by both — always use this

### Spotify API Restrictions (Nov 2024+)
The following endpoints return 403 for new apps without "Extended Quota":
- `/v1/audio-features` (and batch version)
- `/v1/artists?ids=...` (batch)
- `/v1/playlists/{id}/tracks` (deprecated; use `/items`)

**What still works:**
- `/v1/playlists/{id}/items` — track metadata (name, artists, album, release year, duration, explicit)
- Individual `/v1/artists/{id}` — but no genres field returned
- Audio features require Extended Quota application (no free alternative for this pipeline)

Workaround for genres: Last.fm API (free, no OAuth) — use `artist.getTopTags`. See `docs/spotify-api-research.md`.

### Credentials
Stored in `.env` (gitignored). Do not commit. Do not print or log.

---

## Suno Integration

### Authentication (Confirmed Working)

Suno uses Clerk for auth. Two token layers:
1. `__client` — long-lived JWT in `.refrakt/suno_session.json` (expires ~2027)
2. Short-lived JWT — refreshed per-request via Clerk

**JWT Refresh (confirmed pattern):**
```python
import requests, json

with open(".refrakt/suno_session.json") as f:
    session = json.load(f)

r = requests.post(
    f"https://auth.suno.com/v1/client/sessions/{session['session_id']}/tokens",
    headers={
        "Cookie": f"__client={session['client_token']}",
        "Origin": "https://suno.com",
    },
    params={"_clerk_js_version": "5.36.2"},
)
jwt = r.json()["jwt"]
```

**Auth domain:** `auth.suno.com` (NOT `clerk.suno.com` — doc was wrong)
**API base:** `https://studio-api.prod.suno.com` (NOT `studio-api.suno.ai` — doc was wrong)

### Generate Endpoint

```
POST https://studio-api.prod.suno.com/api/generate/v2-web/
Authorization: Bearer {jwt}
Cookie: sessionid={django_session_id}
Content-Type: application/json
```

**Request body (confirmed format):**
```json
{
  "token": "P1_...",
  "generation_type": "TEXT",
  "title": "Your Invented Title",
  "tags": "ambient electronic, IDM, instrumental, atmospheric, synthesizer, 120bpm",
  "negative_tags": "",
  "mv": "chirp-crow",
  "prompt": "",
  "make_instrumental": true,
  "user_uploaded_images_b64": null,
  "metadata": {
    "web_client_pathname": "/create",
    "is_max_mode": false,
    "is_mumble": false,
    "create_mode": "custom",
    "user_tier": "3eaebef3-ef46-446a-931c-3d50cd1514f1",
    "create_session_token": "ec0dfbcd-5b3d-47d7-abc2-09cb1f9a6770",
    "disable_volume_normalization": false,
    "can_control_sliders": ["weirdness_constraint", "style_weight"]
  },
  "override_fields": [],
  "transaction_uuid": "d102192f-7638-40a0-9a92-ad81384b15ec"
}
```

### hCaptcha Behavior (Updated Feb 24 2026)

The generate endpoint requires a valid hCaptcha `token` field. Without it → 422 "Token validation failed". However, the hCaptcha is configured as an **invisible widget** with a **heartbeat action** — it runs silently in the browser and auto-generates tokens without user interaction when the risk score is low.

**When does the visual challenge appear?**
- The invisible captcha evaluates browser fingerprint, automation flags, and session history
- **Playwright `--headed` with in-memory profile:** Visual challenge appears (image grid). hCaptcha detects `navigator.webdriver=true` and the fresh profile.
- **Playwright `--headed --persistent` with persistent profile:** No visual challenge. The invisible widget auto-passes and tokens are generated silently. Both songs in a 2-song batch submitted without any captcha.
- **Direct API calls from Python:** No browser = no hCaptcha widget = no token at all → 422.

**Current working approach:**
1. Open `playwright-cli --headed --persistent --profile=.refrakt/playwright-profile` to `suno.com/create`
2. Inject session cookies from `.refrakt/suno_session.json`
3. Switch to Custom mode, fill style tags + title, click Create
4. The invisible hCaptcha auto-generates the token — no user interaction needed
5. Poll and download via `suno.py download`

**Browser automation attempt history:**

| Attempt | Browser | Profile | Captcha? | Result |
|---------|---------|---------|----------|--------|
| 1 | Playwright `--headed` | In-memory | Visual grid challenge | Had to solve manually |
| 2 | Playwright `--headed --persistent` | Persistent | No challenge (invisible auto-pass) | 2 songs submitted, 0 captchas |

**Persistent profile location:** `.refrakt/playwright-profile/` (project-relative, gitignored)

### Polling

```python
r = requests.get(
    f"https://studio-api.prod.suno.com/api/feed/?ids={ids_param}",
    headers={
        "Authorization": f"Bearer {jwt}",
        "Cookie": f"sessionid={django_session}",
    },
)
```

Poll every 5s. Status goes: `submitted` → `running` → `complete`.

### Audio Download

Two formats available per clip on the CDN (both public, no auth needed, permanent URLs):

| Format | URL pattern | Quality | Used by |
|--------|-------------|---------|---------|
| MP3 | `https://cdn1.suno.ai/{clip_id}.mp3` | 64 kbps, 48 kHz stereo | API `audio_url` field |
| M4A (Opus) | `https://cdn1.suno.ai/{clip_id}.m4a` | ~143 kbps, 48 kHz stereo | Web player; **preferred** |

All download scripts in this project use `.m4a` by default for higher quality.

### Current Model

`chirp-crow` = v5 (the latest as of Feb 2026). Session refers to it as "v4.5" in some fields, but `mv` field is `chirp-crow`.

### Credits

- 10 credits per generation (= 2 clips)
- Pro tier: 2500 credits/month
- Balance: 2460 credits remaining (used 40 total: 4 generations × 10 credits)

---

## Title Convention

**Generated song titles must NOT reference the original Spotify track name.** Use the original as thematic inspiration only, and invent a new title. This prevents guard rails on generation.

Example: "Semi Detached" → something like "Hollow Transit" or "Glass Quarter" (same mood, new name).

---

## File Conventions

- CLI entry points: `bin/` — executable scripts (no `.py` extension), add to `$PATH`
- Library modules: `lib/` (`suno.py`, `generate_prompts.py`, etc.) — importable, paths resolve via `__file__`
- Output data: `playlist_data.json` (gitignored)
- Working data: `.refrakt/` (gitignored) — caches, session, browser profile
  - `.refrakt/caches/lastfm.json` — Last.fm genre cache (auto-created by `enrich_genres.py`)
  - `.refrakt/caches/prompt_research.json` — Perplexity research cache (auto-created by `generate_prompts.py`)
  - `.refrakt/caches/playlist.json` — Spotify playlist cache (24-hour TTL, avoids rate limits)
  - `.refrakt/suno_session.json` — Suno auth session
  - `.refrakt/playwright-profile/` — persistent browser profile (captcha-free Suno submission)
  - `.refrakt/playwright-cli/` — Playwright traces and downloads
- Temp audio (candidates): `SUNO_TEMP_DIR` (from `.env`, default `~/Google Drive/My Drive/SunoTemp/`)
  - Structure: `SUNO_TEMP_DIR/YYYY-MM-DD/{Title}__{clip_id}.m4a`
  - All 6 candidates (3 prompt variations × 2 clips) go here
  - Audio-critic evaluates, picks best, copies winner to `output/`
  - Also stores: research files, batch prompts, eval results, album art, track journals
  - **All temp/working files go here** — never leave `_`-prefixed files in project root
- Final audio: `output/YYYY-MM-DD/{Title}.m4a` — clean filename, no timestamp prefix, no clip ID
  - For albums: `output/{Album Name}/##_{Title}.m4a`
- Generated track tracking: `generated_tracks.json` (tracks which source tracks have been submitted)
- Documentation: `docs/` with screenshots in `docs/images/`
- Skills: `.claude/skills/{name}/SKILL.md` — reusable pipeline actions with YAML frontmatter
- Always use `.venv/bin/python` (not system python) when running `.py` files directly

---

## Running the Project

All CLI commands are in `bin/`. Add to `$PATH` or run from project root.

```bash
# Full pipeline (end-to-end: prompts -> browser -> poll -> download)
bin/suno-generate --count 2              # generate 2 songs
bin/suno-generate --count 5 --seed 42    # reproducible batch of 5
bin/suno-generate --count 1 --no-download  # submit only, download later

# Individual pipeline steps
bin/fetch-playlist                       # Step 1a: fetch Spotify playlist data
bin/enrich-genres                        # Step 1b: enrich with Last.fm genre tags
bin/generate-prompts --count 10          # Step 2a: research tracks + generate rich prompts (instrumental)
bin/refrakt --playlist "Rocket" --track "Name"  # Step 2b: Refrakt — vocal refraction from any playlist

# Browser form fill (used during /suno-generate Phase 3)
bin/suno-fill-form                       # fill form from prompts_data.json (index 0)
bin/suno-fill-form --index 1             # fill specific prompt
bin/suno-fill-form --dry-run             # preview without browser

# Suno operations
bin/suno auth                            # verify session and show user/credit info
bin/suno credits                         # show remaining credits
bin/suno feed [--page N]                 # list recent clips
bin/suno poll <clip_id> --wait           # poll clip status until complete
bin/suno download <clip_id> ...          # download completed clips (.m4a)

# Metadata tagging
bin/suno-tag --all                       # retro-tag all .m4a files in output/
bin/suno-tag --all --dry-run             # preview without writing
bin/suno-tag <clip_id> ...               # tag specific clips by ID prefix

# Standalone download
bin/download-tracks <clip_id> ...        # download clips (standalone utility)
```

---

## Browser Automation Notes

This project uses `playwright-cli` (with `--headed` flag) for interactive browser tasks.

- React checkboxes often need JS eval: `playwright-cli run-code "async page => page.evaluate(() => document.getElementById('accepted').click())"`
- Use `playwright-cli network` to capture API calls while interacting with the UI
- Captured traces go to `.refrakt/playwright-cli/traces/`
- The `resources/` subdirectory of a trace contains API response JSON files
