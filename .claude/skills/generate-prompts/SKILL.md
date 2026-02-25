---
name: generate-prompts
description: Generate Suno prompts from enriched playlist data
allowed-tools: Bash(bin/generate-prompts *)
user-invocable: true
argument-hint: "[--count N] [--seed SEED]"
---

# /generate-prompts — Generate Suno Prompts

Creates Suno AI generation prompts from enriched playlist track data.

## What it does

1. Reads tracks from `playlist_data.json` (must have `genres` field from enrichment)
2. Randomly selects N tracks that haven't already been generated
3. For each selected track, creates a prompt with an invented title and style tags
4. Outputs prompts to `prompts_data.json`

## Command

```bash
bin/generate-prompts [--count N] [--seed SEED]
```

- `--count N` — number of prompts to generate (default: 10)
- `--seed SEED` — random seed for reproducibility

## Prerequisites

- `playlist_data.json` must exist with `genres` field (run `/enrich` first)

## Title convention

Generated titles must NOT reference the original track name — uses invented abstract titles to avoid Suno guard rails.
