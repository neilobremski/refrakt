---
name: suno-status
description: Check Suno auth, credits, feed, and clip status
allowed-tools: Bash(bin/suno *)
user-invocable: true
argument-hint: "{auth|credits|feed|poll}"
---

# /suno-status — Check Suno Auth and Credits

Verifies Suno session authentication and shows remaining credits, feed, or clip status.

## Commands

```bash
bin/suno auth              # Verify session and show user/credit info
bin/suno credits           # Show remaining credits
bin/suno feed [--page N]   # List recent clips
bin/suno poll <id> --wait  # Poll clip status until complete
```

## Prerequisites

- `.refrakt/suno_session.json` must exist with valid `session_id`, `client_token`, and `django_session_id`

## Credit math

- 10 credits per generation (produces 2 clips)
- Pro tier: 2,500 credits/month (250 generations)
