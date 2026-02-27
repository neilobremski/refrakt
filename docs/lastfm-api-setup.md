# Last.fm API Setup

How to get a free Last.fm API key for genre tag lookups.

## Prerequisites

- A Last.fm account (free at https://www.last.fm/join)

## Steps

### 1. Go to the API account creation page

Navigate to: https://www.last.fm/api/account/create

If you're not logged in, Last.fm will redirect you to the login page first.

### 2. Fill out the form

| Field | What to enter |
|-------|---------------|
| **Contact email** | Pre-filled with your Last.fm account email |
| **Application name** | Any name (e.g., "Refrakt") |
| **Application description** | Brief description of what you're using it for |
| **Callback URL** | Leave blank (not needed for server-side API calls) |
| **Application homepage** | Your GitHub profile or project URL |

### 3. Solve the reCAPTCHA and submit

Click "I'm not a robot", then click **Submit**.

### 4. Copy your API key

The confirmation page shows:

- **API key** — this is what you need (32-character hex string)
- **Shared secret** — only needed for authenticated write operations (not needed for `artist.getTopTags`)

### 5. Add the key to `.env`

```
LASTFM_API_KEY=your_api_key_here
```

## Managing your API account

View or edit your API accounts at: https://www.last.fm/api/accounts

## API usage in this project

We use a single endpoint:

```
GET https://ws.audioscrobbler.com/2.0/
    ?method=artist.getTopTags
    &artist={artist_name}
    &api_key={your_key}
    &format=json
    &autocorrect=1
```

This returns the top genre/style tags for an artist. The API is free with no hard rate limit, but Last.fm asks that you stay under ~5 requests/second. Our `enrich_genres.py` script uses a 0.2s delay between requests and caches results to `.refrakt/caches/lastfm.json`.

## Rate limits

- No published hard limit for read-only endpoints
- Recommended: max 5 requests/second
- No daily quota for `artist.getTopTags`
- No OAuth needed — API key in query string is sufficient
