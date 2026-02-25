---
name: suno-tag
description: Tag M4A files with Suno clip metadata (title, genre, cover art)
allowed-tools: Bash(bin/suno-tag *), Bash(bin/suno feed *)
user-invocable: true
argument-hint: "[--all] [--dry-run] [clip_id ...]"
---

# /suno-tag — Tag M4A Files with Metadata

Tags downloaded M4A files in `output/` with metadata from the Suno feed API: title, artist, album, genre (style tags), year, comment (clip ID + model), description (source track), and cover art (JPEG).

## Usage

```bash
# Tag all files in output/
bin/suno-tag --all

# Preview what would be tagged
bin/suno-tag --all --dry-run

# Tag specific clips by ID prefix
bin/suno-tag 0492fab7 46ba57f9
```

## What Gets Tagged

| Field | Value |
|-------|-------|
| Title | Clip title from Suno |
| Artist | "Suno AI" |
| Album | "Wordless Work (Suno)" |
| Genre | Style tags from clip metadata |
| Year | Year from created_at |
| Comment | `suno:{clip_id} model:{model_name}` |
| Description | Source track info from prompts_data.json |
| Cover Art | JPEG from clip's image_large_url |

## How It Works

1. Scans `output/` for `.m4a` files
2. Extracts 8-char clip ID prefix from each filename (`__{prefix}.m4a`)
3. Fetches Suno feed (up to 10 pages) to resolve full clip metadata
4. Matches clips to prompts_data.json entries by title (for source track info)
5. Writes MP4 atoms using mutagen

## Prerequisites

- `.suno_session.json` with valid session (for feed API access)
- `mutagen` installed in `.venv` (`pip install mutagen`)
- `prompts_data.json` (optional — for source track descriptions)
