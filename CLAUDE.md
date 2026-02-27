# CLAUDE.md — Project Context for Claude Code

## Project Goal

Build an end-to-end pipeline:

1. Read the Spotify playlist **"Wordless Work"** (private playlist belonging to the user)
2. Analyze each track's audio features, genres, and overall vibe
3. Generate a Suno AI style prompt per track — with an **invented title** (not derived from the original track name, to avoid guard rails)
4. Submit each prompt to Suno AI, wait for generation to complete
5. Download the resulting MP3s to `OUT_DIR` (`~/Downloads/` by default)
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
- First test generation completed: 2 clips generated, downloaded to `OUT_DIR`
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
  - All creative agents use `bin/prompts` CLI for safe JSON manipulation (not direct file Edit/Write)
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
- `bin/prompts` — safe CLI for `prompts_data.json` manipulation (used by all creative agents)
  - Subcommands: `list`, `count`, `get`, `set`, `delete`
  - Atomic writes (temp file + rename) prevent JSON corruption
  - `--stdin` flag for multi-line lyrics, `--json` flag for structured values (lists, objects)
  - All creative agents (lyricist, producer, title-designer, title-critic) use `Bash(bin/prompts *)` instead of direct `Read`/`Edit`/`Write` on JSON files
- `.claude/agents/suno.md` — Haiku agent for Suno browser automation and submission
  - Consolidates all Suno knowledge: auth, hCaptcha, React form quirks, prompt variation strategy
  - Handles: open browser → inject cookies → create 3 prompt variations → fill/submit → poll → download
  - Knows about Advanced Options (male/female selector, exclude styles)
- `bin/suno submit` — one-command browser automation for Suno submission
  - Opens browser, injects cookies, creates 3 tag variations, fills/submits each, closes browser
  - Auto-discovers new clip IDs via feed diffing; optional `--no-download` flag
  - Replaces manual playwright-cli orchestration with a single pre-approvable command
- `bin/refrakt-check` — post-pipeline completion validator
  - Checks 8 steps: tags, lyrics, title, WIP candidates (6), output, cover art, album art, tracking
  - Any missing step → exit 1; ALL CLEAR → exit 0. Run as final phase of every pipeline.
- `lib/gemini_image.py` — Gemini API album art generation (square + widescreen)
- `.claude/agents/artist.md` — Haiku agent for album/track artwork via Gemini (Nano Banana)
  - Generates square (1:1, ~2048px) for metadata and widescreen (16:9, ~2752px) for YouTube
  - Can use `lib/gemini_image.py` (API) or browser automation at gemini.google.com
  - Spawnable in background while other post-eval work proceeds
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
- Audio-critic evaluates all 6 → auto-picks the best → copies to `OUT_DIR/YYYY-MM-DD/`
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

Full Suno knowledge (auth, API, hCaptcha, browser automation, React form quirks, prompt variation strategy) is in `.claude/agents/suno.md`. Key quick-reference:

- **Auth:** Clerk-based. Session in `.refrakt/suno_session.json`. JWT refresh via `auth.suno.com`.
- **API base:** `https://studio-api.prod.suno.com`
- **CDN:** `https://cdn1.suno.ai/{clip_id}.m4a` (public, no auth, Opus ~143kbps preferred)
- **Browser:** Always use `playwright-cli --headed --persistent --profile=.refrakt/playwright-profile` (captcha-free)
- **Model:** `chirp-crow` = v5 (latest as of Feb 2026)
- **Credits:** 10 per generation (= 2 clips). Pro tier: 2500/month.
- **CLI:** `bin/suno auth|credits|feed|poll|download|submit`, `bin/suno-fill-form`, `bin/prompts`
- **Submit:** `bin/suno submit --index 0` — one command for 3 variations × 2 clips = 6 candidates

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
- WIP audio (candidates): `WIP_DIR` (from `.env`, default `~/Google Drive/My Drive/SunoTemp/`)
  - Structure: `WIP_DIR/YYYY-MM-DD/{Title}__{clip_id}.m4a`
  - All 6 candidates (3 prompt variations × 2 clips) go here
  - Audio-critic evaluates, picks best, copies winner to `OUT_DIR`
  - Also stores: research files, batch prompts, eval results, album art, track journals
  - **All temp/working files go here** — never leave `_`-prefixed files in project root
- Final audio: `OUT_DIR/YYYY-MM-DD/{Title}.m4a` (from `.env`, default `~/Downloads/`) — clean filename, no timestamp prefix, no clip ID
  - For albums: `OUT_DIR/{Album Name}/##_{Title}.m4a`
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

# Prompt data manipulation (used by creative agents)
bin/prompts list                         # summary table of all entries
bin/prompts count                        # number of entries
bin/prompts get 0                        # full entry as pretty JSON
bin/prompts get 0 tags                   # single field value (raw text)
bin/prompts set 0 tags "new tags"        # set a scalar field
echo "lyrics" | bin/prompts set 0 prompt --stdin  # set from stdin (multi-line)
bin/prompts set 0 _title_candidates --json '[...]' # set structured value
bin/prompts delete 0 _title_rejected     # remove a field

# Browser form fill (used during /suno-generate Phase 3)
bin/suno-fill-form                       # fill form from prompts_data.json (index 0)
bin/suno-fill-form --index 1             # fill specific prompt
bin/suno-fill-form --dry-run             # preview without browser

# Suno operations
bin/suno auth                            # verify session and show user/credit info
bin/suno credits                         # show remaining credits
bin/suno feed [--page N]                 # list recent clips
bin/suno submit --index 0               # submit with 3 tag variations (browser automation)
bin/suno submit --index 0 --no-download # submit only, download later
bin/suno poll <clip_id> --wait           # poll clip status until complete
bin/suno download <clip_id> ...          # download completed clips (.m4a)

# Metadata tagging
bin/suno-tag --all                       # retro-tag all .m4a files in output/
bin/suno-tag --all --dry-run             # preview without writing
bin/suno-tag <clip_id> ...               # tag specific clips by ID prefix

# Standalone download
bin/download-tracks <clip_id> ...        # download clips (standalone utility)

# Pipeline validation
bin/refrakt-check                        # check all entries for completeness
bin/refrakt-check --index 0              # check specific entry
```

---

## Browser Automation Notes

This project uses `playwright-cli` (with `--headed` flag) for interactive browser tasks. Suno-specific browser knowledge is in `.claude/agents/suno.md`.

- React checkboxes often need JS eval: `playwright-cli run-code "async page => page.evaluate(() => document.getElementById('accepted').click())"`
- Use `playwright-cli network` to capture API calls while interacting with the UI
- Captured traces go to `.refrakt/playwright-cli/traces/`
- The `resources/` subdirectory of a trace contains API response JSON files
