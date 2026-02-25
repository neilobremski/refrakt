---
name: fetch-playlist
description: Fetch Spotify playlist track data
allowed-tools: Bash(bin/fetch-playlist *)
user-invocable: true
argument-hint: ""
---

# /fetch-playlist — Fetch Spotify Playlist Data

Fetches all tracks from the "Wordless Work" Spotify playlist and saves metadata to `playlist_data.json`.

## Command

```bash
bin/fetch-playlist
```

## Prerequisites

- `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI` in `.env`
- On first run, a browser will open for Spotify OAuth

## Output

- `playlist_data.json` — track metadata (name, artists, album, release year, duration, popularity)
