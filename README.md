# Refrakt

An automated pipeline that reads a Spotify playlist, analyzes each track's musical DNA, and uses that data to generate and download original instrumental music via Suno AI.

## What It Does

1. **Fetch playlist** — Pulls all tracks from a named Spotify playlist (track metadata only — audio features and genres are no longer available without Spotify Extended Quota)
   1a. **Enrich genres** — Queries Last.fm `artist.getTopTags` for each unique artist to add genre tags to every track
2. **Generate prompts** — Maps each track's audio characteristics to a Suno AI style prompt with invented titles
3. **Generate music** — Submits prompts to Suno AI via headed browser automation, polls for completion
4. **Download audio** — Saves generated clips as `.m4a` (Opus ~143kbps) with timestamp-prefixed filenames
5. **Tag files** — Writes ID3 metadata (title, album art, etc.) to downloaded files (planned)

The target playlist is **"Wordless Work"** — a curated collection of instrumental and ambient tracks. The goal is to generate a set of original Suno-composed instrumentals that capture a similar mood and feel.

## Project Structure

```
Refrakt/
├── bin/                        # CLI entry points (executable, no .py extension)
│   ├── suno-generate           # Full pipeline: prompts -> browser -> poll -> download
│   ├── fetch-playlist          # Fetch Spotify playlist data
│   ├── enrich-genres           # Enrich tracks with Last.fm genre tags
│   ├── generate-prompts        # Generate Suno prompts from enriched data
│   ├── suno                    # Suno CLI: auth, credits, feed, poll, download
│   └── download-tracks         # Standalone clip downloader
├── lib/
│   ├── suno.py                 # Suno API library (auth, feed, poll, download)
│   ├── generate_prompts.py     # Prompt generation library (titles, tags, tracking)
│   ├── fetch_playlist.py       # Spotify playlist fetch library
│   ├── enrich_genres.py        # Last.fm genre enrichment library
│   └── download_tracks.py      # Standalone download library
├── .env                        # Spotify + Last.fm credentials (gitignored)
├── .gitignore
├── .venv/                      # Python virtual environment (gitignored)
├── .suno_session.json          # Suno auth tokens (gitignored)
├── .lastfm_cache.json          # Last.fm tag cache (gitignored, auto-created)
├── .claude/
│   └── skills/                 # Claude Code skills (SKILL.md frontmatter pattern)
│       ├── suno-generate/
│       ├── fetch-playlist/
│       ├── enrich/
│       ├── generate-prompts/
│       ├── suno-status/
│       └── suno-download/
├── playlist_data.json          # Track data, updated by enrich_genres.py (gitignored)
├── generated_tracks.json       # Tracks which source tracks have been submitted
├── output/                     # Downloaded audio — .m4a preferred (gitignored)
└── docs/
    ├── spotify-api-setup.md
    ├── spotify-api-research.md
    ├── suno-api-research.md
    └── images/
```

## Setup

### Prerequisites

- Python 3.10+
- A Spotify account
- A Spotify Developer App (see [docs/spotify-api-setup.md](docs/spotify-api-setup.md))
- A Last.fm API key (free — register at https://www.last.fm/api/account/create)
- A Suno account (for generation step)
- `playwright-cli` installed (for browser automation)

### Install dependencies

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### Configure credentials

Create a `.env` file in the project root:

```
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
LASTFM_API_KEY=your_lastfm_api_key
```

See [docs/spotify-api-setup.md](docs/spotify-api-setup.md) for how to create a Spotify Developer App and obtain these credentials.

## Usage

### Full pipeline (recommended)

```bash
bin/suno-generate --count 2              # generate 2 songs end-to-end
bin/suno-generate --count 5 --seed 42    # reproducible batch of 5
bin/suno-generate --count 1 --no-download  # submit only, download later
```

This runs the entire pipeline: selects un-generated tracks, generates prompts with invented titles, opens a headed browser, fills the Suno form, submits, polls for completion, and downloads results.

### Individual steps

```bash
bin/fetch-playlist               # Step 1a: fetch Spotify playlist data
bin/enrich-genres                # Step 1b: enrich with Last.fm genre tags
bin/generate-prompts --count 10  # Step 2: generate prompt data
```

### Suno operations

```bash
bin/suno auth                    # Verify session and show user/credit info
bin/suno credits                 # Show remaining credits
bin/suno feed [--page N]         # List recent clips
bin/suno poll <id> --wait        # Poll clip status until complete
bin/suno download <id>...        # Download completed clips as .m4a
```

On first Spotify run, a browser window will open for login. If it redirects to an `https://localhost` page with an SSL error, copy the full URL from the address bar and paste it back into the terminal.

## Download filename format

All downloads use the pattern: `YYYYMMDDhhmmss_{title}__{clip_id}.m4a`

Example: `20260224195700_Glass_Circuit__60a3426d.m4a`

## Spotify OAuth Note

This project uses the Authorization Code flow. Spotify credentials are stored in `.cache` after first login — you won't need to log in again on subsequent runs unless the token expires.

## Status

| Step | Status |
|------|--------|
| 1a. Fetch Spotify playlist data | Working |
| 1b. Enrich tracks with Last.fm genre tags | Working |
| 2. Generate Suno prompts from track data + genres | Working |
| 3. Full generation loop (browser automation + poll + download) | Working |
| 4. Download completed clips (.m4a Opus ~143kbps) | Working |
| 5. Tag files with metadata | Planned |

## Suno API

Suno does not have an official public API. Generation uses reverse-engineered session cookie auth with hCaptcha as the main barrier. The pipeline uses `playwright-cli --headed --persistent` with a persistent browser profile — the invisible hCaptcha auto-passes without visual challenges. See `docs/suno-api-research.md` for full details.
