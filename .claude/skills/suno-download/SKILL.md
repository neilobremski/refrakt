---
name: suno-download
description: Download completed Suno clips
allowed-tools: Bash(bin/suno download *), Bash(bin/download-tracks *)
user-invocable: true
argument-hint: "<clip_id> [<clip_id> ...]"
---

# /suno-download — Download Completed Suno Clips

Downloads completed Suno clips to `WIP_DIR` (candidates for evaluation) as `.m4a` (Opus ~143kbps).

## Commands

```bash
bin/suno download <clip_id> [<clip_id> ...]
bin/download-tracks <clip_id> [<clip_id> ...]
```

## Download format

Files are saved as: `YYYYMMDDhhmmss_{title}__{clip_id}.m4a`

## Audio formats

| Format | URL | Quality |
|--------|-----|---------|
| M4A (Opus) | `https://cdn1.suno.ai/{clip_id}.m4a` | ~143 kbps (preferred) |
| MP3 | `https://cdn1.suno.ai/{clip_id}.mp3` | 64 kbps |

## Prerequisites

- `.refrakt/suno_session.json` must exist with valid session
- Clip IDs must be valid UUIDs from Suno generations
