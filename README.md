# Refrakt

Original songs refracted from existing ones. An automated pipeline that analyzes tracks from Spotify playlists, researches their musical character via Perplexity AI, and generates original music through Suno AI — both instrumentals and vocal tracks with newly written lyrics.

## What It Does

### Instrumental pipeline (Wordless Work)

1. **Fetch playlist** — Pulls tracks from a Spotify playlist
2. **Enrich genres** — Queries Last.fm `artist.getTopTags` for genre tags
3. **Research + generate prompts** — Uses Perplexity AI to research each track's sonic character, then synthesizes rich Suno style tags (120-200 chars with textures, mood, BPM) and structural metatags
4. **Generate music** — Submits prompts to Suno AI via headed browser automation, polls for completion
5. **Download + tag** — Saves clips as `.m4a` (Opus ~143kbps) and writes metadata (title, artist, genre, cover art)

### Vocal refraction pipeline (Refrakt)

1. **Pick a track** from any Spotify playlist
2. **Fetch original lyrics** from Genius
3. **Research** the track's musical character via Perplexity AI
4. **Generate style tags** — same Perplexity-powered synthesis as instrumentals
5. **Write refracted lyrics** — an AI agent (Haiku) reads the original lyrics and writes completely new ones that capture the same spirit with fresh imagery
6. **Generate + download + tag** — same Suno submission pipeline as above

All generated metadata is credited to artist **"Refrakt"**.

## Project Structure

```
Refrakt/
├── bin/                        # CLI entry points (executable, no .py extension)
│   ├── suno-generate           # Full pipeline: prompts -> browser -> poll -> download
│   ├── refrakt                 # Vocal refraction pipeline
│   ├── fetch-playlist          # Fetch Spotify playlist data
│   ├── enrich-genres           # Enrich tracks with Last.fm genre tags
│   ├── generate-prompts        # Research tracks + generate rich prompts
│   ├── suno                    # Suno CLI: auth, credits, feed, poll, download
│   ├── suno-tag                # M4A metadata tagging
│   └── download-tracks         # Standalone clip downloader
├── lib/
│   ├── suno.py                 # Suno API library (auth, feed, poll, download)
│   ├── generate_prompts.py     # Perplexity research + prompt synthesis
│   ├── refrakt.py              # Vocal refraction pipeline
│   ├── perplexity.py           # Perplexity AI REST client
│   ├── genius.py               # Genius lyrics fetcher
│   ├── fetch_playlist.py       # Spotify playlist fetch
│   ├── enrich_genres.py        # Last.fm genre enrichment
│   ├── tag_tracks.py           # M4A metadata tagging (mutagen)
│   └── download_tracks.py      # Audio download utility
├── .claude/
│   ├── agents/
│   │   └── refrakt.md          # Haiku agent for lyric refraction
│   ├── settings.json           # Claude Code permissions and hooks
│   └── skills/                 # Claude Code skills (SKILL.md frontmatter)
│       ├── suno-generate/
│       ├── fetch-playlist/
│       ├── enrich/
│       ├── generate-prompts/
│       ├── suno-status/
│       ├── suno-download/
│       └── suno-tag/
├── docs/
│   ├── spotify-api-setup.md
│   ├── spotify-api-research.md
│   ├── suno-api-research.md
│   └── lastfm-api-setup.md
├── requirements.txt
├── .gitignore
├── .env                        # API credentials (gitignored)
├── .suno_session.json          # Suno auth tokens (gitignored)
└── output/                     # Downloaded audio (gitignored)
```

## Setup

### Prerequisites

- Python 3.10+
- A Spotify Developer App (see [docs/spotify-api-setup.md](docs/spotify-api-setup.md))
- A Last.fm API key (free — [register here](https://www.last.fm/api/account/create))
- A Perplexity API key (for track research — [perplexity.ai](https://www.perplexity.ai))
- A Genius API token (for lyrics — [genius.com/api-clients](https://genius.com/api-clients))
- A Suno account (for generation)
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
PERPLEXITY_API_KEY=your_perplexity_api_key
GENIUS_ACCESS_TOKEN=your_genius_token
```

## Usage

### Instrumental generation (end-to-end)

```bash
bin/suno-generate --count 2              # generate 2 songs
bin/suno-generate --count 5 --seed 42    # reproducible batch of 5
bin/suno-generate --count 1 --no-download  # submit only, download later
```

### Vocal refraction (Refrakt)

```bash
bin/refrakt --playlist "Rocket" --track "Retrovertigo"   # specific track
bin/refrakt --playlist "Rocket" --random                  # random track
bin/refrakt --playlist "Rocket" --list                    # browse tracks
```

After `bin/refrakt` generates the prompt data, spawn the Refrakt agent to write lyrics, then run `/suno-generate` to submit.

### Individual pipeline steps

```bash
bin/fetch-playlist               # Fetch Spotify playlist data
bin/enrich-genres                # Enrich with Last.fm genre tags
bin/generate-prompts --count 10  # Research tracks + generate prompts
```

### Suno operations

```bash
bin/suno auth                    # Verify session and show user/credit info
bin/suno credits                 # Show remaining credits
bin/suno feed [--page N]         # List recent clips
bin/suno poll <id> --wait        # Poll clip status until complete
bin/suno download <id>...        # Download completed clips as .m4a
```

### Metadata tagging

```bash
bin/suno-tag --all               # Tag all .m4a files in output/
bin/suno-tag --all --dry-run     # Preview without writing
bin/suno-tag <clip_id> ...       # Tag specific clips
```

## How It Works

### Title invention

Generated song titles are never derived from the original track name (to avoid Suno guard rails). Titles are invented to evoke a similar mood.

Example: "Retrovertigo" by Mr. Bungle -> "Glass Cradle"

### Perplexity-powered research

Each track is researched via Perplexity AI (sonar-pro model) to understand its sonic character — instrumentation, production style, tempo, mood, and cultural context. This research is synthesized into rich, descriptive Suno style tags rather than simple genre labels.

### Download format

All downloads use `.m4a` (Opus ~143kbps) over `.mp3` (64kbps) for higher quality.

Filename pattern: `YYYYMMDDhhmmss_{title}__{clip_id}.m4a`

## Status

| Step | Status |
|------|--------|
| Fetch Spotify playlist data | Working |
| Enrich tracks with Last.fm genre tags | Working |
| Perplexity research + prompt generation | Working |
| Vocal refraction (Refrakt pipeline) | Working |
| Browser automation + poll + download | Working |
| M4A metadata tagging (title, art, genre) | Working |

## Suno API

Suno does not have an official public API. Generation uses reverse-engineered session cookie auth with hCaptcha as the main barrier. The pipeline uses `playwright-cli --headed --persistent` with a project-local browser profile — the invisible hCaptcha auto-passes without visual challenges. See [docs/suno-api-research.md](docs/suno-api-research.md) for full details.
