---
name: enrich
description: Enrich tracks with Last.fm genre tags
allowed-tools: Bash(bin/enrich-genres *)
user-invocable: true
argument-hint: ""
---

# /enrich — Run Last.fm Genre Enrichment

Enriches `playlist_data.json` with genre tags from the Last.fm API.

## What it does

1. Reads all tracks from `playlist_data.json`
2. Collects unique artists
3. Queries Last.fm `artist.getTopTags` for each artist not already cached
4. Filters out non-genre tags (personal tags, star ratings, years)
5. Writes genre tags back to each track in `playlist_data.json`
6. Caches results to `.lastfm_cache.json` (safe to interrupt and re-run)

## Command

```bash
bin/enrich-genres
```

## Prerequisites

- `LASTFM_API_KEY` must be set in `.env`
- `playlist_data.json` must exist (run `/fetch-playlist` first)

## Notes

- Rate limited to ~5 req/s (0.2s delay between API calls)
- Cached artists are skipped, so re-runs are fast
