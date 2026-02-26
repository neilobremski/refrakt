# Refrakt

Original songs refracted from existing ones — plus fully autonomous concept albums. An AI-powered pipeline that analyzes tracks from Spotify playlists, researches their musical character via Perplexity AI, generates original music through Suno AI, evaluates quality with Gemini, creates album art with DALL-E, and publishes to YouTube.

## Albums

### Alive Through the Rift

[![Alive Through the Rift](docs/retrospectives/images/alive-through-the-rift-cover.jpg)](https://youtu.be/Cn2W7uO-zls)

**16 tracks / 42:49 / Futuristic Blues + Industrial Rock**

A post-apocalyptic robot adventurer steps through an interdimensional rift, meets a human girl, and discovers what it means to be alive. Mapped to the Save the Cat beat sheet.

[Watch on YouTube](https://youtu.be/Cn2W7uO-zls) | [Read the retrospective](docs/retrospectives/alive-through-the-rift.md)

### Full Circle

[![Full Circle](docs/retrospectives/images/full-circle-cover.jpg)](https://youtu.be/JrWZt9jNG0o)

**12 tracks / 27:27 / Lo-Fi Americana + Ambient Electronic + Cinematic Post-Rock**

Based on the true story of David Heavens, a homeless man in Santa Monica who offered free help on a neighborhood app and became the caregiver and best friend of Frank, a 91-year-old Navy veteran. Created entirely by the autonomous pipeline.

[Watch on YouTube](https://youtu.be/JrWZt9jNG0o) | [Read the retrospective](docs/retrospectives/full-circle.md)

---

## What It Does

### Refraction Pipeline

Transform songs from any Spotify playlist into original music:

1. **Research** the source track's musical character via Perplexity AI
2. **Write refracted lyrics** — an AI agent creates completely new words that capture the same spirit
3. **Generate vocal-aware style tags** — the suno-prompt agent places vocal descriptors (gender, tone, texture) for accurate voice generation
4. **Name the song** — adversarial title/critic agents argue over the best title (max 2 rounds)
5. **Submit to Suno AI** via browser automation, poll, download
6. **Evaluate with Gemini** — AI listens to each track and scores genre match, mood, production, artistic merit
7. **Tag + transcode** — MP3 (320kbps) for Apple Music, M4A for archival

### Autonomous Album Pipeline (`/autonomous-album`)

Create a full concept album from scratch — no human input needed:

1. **Find a story** — Perplexity searches the news for compelling narratives
2. **Design the soundtrack** — Save the Cat beat mapping, sonic palette research, lyrics for vocal tracks
3. **Generate album art** — DALL-E 3 creates square + widescreen covers
4. **Generate all tracks** via Suno, evaluate with Gemini, auto-select best versions
5. **Package** — tag metadata, embed cover art, concatenate full album
6. **Upload to YouTube** — create video, fill metadata, publish

**~45 minutes from news headline to YouTube. ~$0.18 in API costs per album.**

## Project Structure

```
Refrakt/
├── bin/                        # CLI entry points
│   ├── suno-generate           # Full pipeline: prompts -> browser -> poll -> download
│   ├── refrakt                 # Vocal refraction pipeline
│   ├── suno-fill-form          # Browser form fill helper
│   ├── suno                    # Suno CLI: auth, credits, feed, poll, download
│   ├── suno-tag                # M4A/MP3 metadata tagging
│   ├── fetch-playlist          # Fetch Spotify playlist data
│   ├── enrich-genres           # Enrich tracks with Last.fm genre tags
│   ├── generate-prompts        # Research tracks + generate rich prompts
│   └── download-tracks         # Standalone clip downloader
├── lib/
│   ├── suno.py                 # Suno API library (auth, feed, poll, download, transcode)
│   ├── refrakt.py              # Vocal refraction pipeline (with playlist cache)
│   ├── gemini_audio.py         # Gemini 2.5 Flash audio evaluation
│   ├── dalle_art.py            # DALL-E 3 album art generation
│   ├── perplexity.py           # Perplexity AI REST client
│   ├── genius.py               # Genius lyrics fetcher
│   ├── generate_prompts.py     # Perplexity research + prompt synthesis
│   ├── tag_tracks.py           # Metadata tagging (mutagen)
│   └── ...
├── .claude/
│   ├── agents/
│   │   ├── refrakt.md          # Haiku agent: write refracted lyrics
│   │   ├── suno-prompt.md      # Haiku agent: generate vocal-aware style tags
│   │   ├── song-title.md       # Haiku agent: generate creative song titles
│   │   ├── song-critic.md      # Haiku agent: adversarial title evaluation
│   │   └── code-reviewer.md    # Sonnet agent: security + quality code review
│   └── skills/
│       ├── autonomous-album/   # Full autonomous album pipeline
│       ├── refrakt-soundtrack/  # Concept album creation
│       ├── youtube-upload/     # YouTube browser automation
│       ├── suno-generate/      # Interactive Suno generation
│       └── ...
├── docs/
│   ├── retrospectives/         # Album write-ups with learnings
│   │   ├── alive-through-the-rift.md
│   │   ├── full-circle.md
│   │   └── images/
│   ├── suno-vocal-prompting.md # Vocal tag reference guide
│   └── ...
├── output/                     # Generated audio (gitignored)
│   ├── Alive Through the Rift/ # First concept album
│   ├── Full Circle/            # Second concept album (autonomous)
│   └── *.mp3 / *.m4a          # Individual refracted tracks
└── requirements.txt
```

## Setup

### Prerequisites

- Python 3.10+
- `playwright-cli` (for browser automation)
- API keys for: Spotify, Last.fm, Perplexity, Genius, Gemini, OpenAI (DALL-E)
- A Suno Pro account (2,500 credits/month)

### Install

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### Configure

Create `.env` in the project root:

```
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
LASTFM_API_KEY=...
PERPLEXITY_API_KEY=...
GENIUS_ACCESS_TOKEN=...
GEMINI_API_KEY=...
OPENAI_API_KEY=...
```

## Usage

### Quick start: refract a song

```bash
bin/refrakt --playlist "Rocket" --random
# Then spawn agents for lyrics, tags, titles, and submit to Suno
```

### Create an autonomous album

```bash
# Run the /autonomous-album skill in Claude Code
# It finds a news story, writes a soundtrack, generates everything, uploads to YouTube
```

### Suno operations

```bash
bin/suno auth                    # Verify session
bin/suno credits                 # Check balance
bin/suno feed                    # List recent clips
bin/suno download <id>...        # Download clips (M4A + MP3 transcode)
```

## How It Works

### AI Agent Pipeline

The pipeline uses specialized Claude Code agents that work in sequence:

1. **Refrakt agent** (Haiku) — writes completely original lyrics from source material
2. **Suno-prompt agent** (Haiku) — generates vocal-aware style tags with gender/tone/texture
3. **Song-title agent** (Haiku) — proposes 3 creative title candidates per track
4. **Song-critic agent** (Haiku) — adversarial evaluation, approves or rejects with feedback
5. **Code-reviewer agent** (Sonnet) — security/quality review before every git push

### Quality Evaluation

After Suno generates music, **Gemini 2.5 Flash** listens to each track and evaluates:
- Vocal contamination (for instrumental tracks)
- Genre match against intended style tags
- Mood alignment with the story beat
- Production quality
- Artistic interest

Cost: ~$0.004 per track evaluation.

### Album Art

**DALL-E 3** generates two versions:
- Square (1024x1024) — embedded in MP3 metadata for Apple Music
- Widescreen (1792x1024) — used for YouTube video thumbnail

### Browser Automation

Suno and YouTube don't have public APIs. The pipeline uses `playwright-cli` with a persistent browser profile for:
- Suno form filling (via `bin/suno-fill-form` with Playwright's locator API)
- YouTube Studio uploads (file input + metadata filling)

The persistent profile ensures hCaptcha auto-passes on Suno without visual challenges.

## Status

| Capability | Status |
|-----------|--------|
| Spotify playlist fetch + cache | Working |
| Last.fm genre enrichment | Working |
| Perplexity research + prompt generation | Working |
| Vocal refraction (original lyrics) | Working |
| Vocal-aware tag generation | Working |
| Adversarial song naming | Working |
| Suno browser submission + download | Working |
| MP3 transcode (320kbps for Apple Music) | Working |
| Gemini audio evaluation | Working |
| DALL-E album art generation | Working |
| Autonomous album creation | Working |
| YouTube upload | Working |
| Code review before push | Working |

## License

This is a personal project. The generated music is created via Suno AI and subject to their terms of service.
