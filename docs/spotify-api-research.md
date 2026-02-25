# Spotify Web API Research: Current State (Early 2026)

> **Research date:** February 2026
> **Scope:** Restrictions affecting new developer apps, restricted endpoints, quota extension process, and alternative data sources
> **Confidence notation:** [CONFIRMED] = documented in official Spotify announcements / developer docs; [COMMUNITY] = widely reported by developers but not in official docs; [SPECULATIVE] = inferred or uncertain

---

## 1. November 2024 Spotify Web API Changes

### Official Announcement

On **27 November 2024**, Spotify published a blog post titled "Changes to the Web API" at:
`https://developer.spotify.com/blog/2024-11-27-changes-to-the-web-api`

This was the most significant restriction to the Spotify Web API since the platform launched. The changes took effect immediately for new apps and were scheduled to roll out to existing apps on a deprecation timeline.

### What Changed [CONFIRMED]

Spotify introduced a two-tier access model:

| Tier | Description |
|------|-------------|
| **Development Mode (default)** | All new apps start here. Restricted to 25 users max (must be manually allowlisted in the dashboard). Access to a reduced set of endpoints. |
| **Extended Quota Mode** | Requires an application and approval from Spotify. Unlocks the full endpoint set and removes the 25-user cap. |

The key motivation cited by Spotify was protecting user data and preventing misuse of audio analysis and recommendation data by third-party AI/ML training pipelines.

### Endpoints Moved to Extended Access Only [CONFIRMED]

The following endpoints were restricted to apps with Extended Quota Mode approval. New apps in Development Mode receive **HTTP 403 Forbidden** on these endpoints:

**Audio Analysis / Features:**
- `GET /v1/audio-features` (batch — up to 100 tracks)
- `GET /v1/audio-features/{id}` (single track)
- `GET /v1/audio-analysis/{id}` (full beat/segment/tatum analysis)

**Recommendations:**
- `GET /v1/recommendations` (seed-based track recommendations)

**Artist / Genre Data (batch):**
- `GET /v1/artists?ids=...` (batch artist lookup — returns 403 for new apps)

**Note on single artist endpoint:** `GET /v1/artists/{id}` (single) appears to return HTTP 200 for new apps, but the `genres` array in the response is either empty (`[]`) or omitted entirely. This is consistent with [COMMUNITY] reports of Spotify silently stripping genre data from single-artist responses for Development Mode apps, even though the endpoint itself is not fully blocked. The behaviour may be endpoint-specific throttling rather than a full 403.

**Playlist endpoint rename (separate from November 2024):**
- `GET /v1/playlists/{id}/tracks` — deprecated (returns 403 or redirect for some apps); replaced by `GET /v1/playlists/{id}/items`
- The `/tracks` → `/items` rename was a separate, earlier deprecation (circa 2023–2024), not part of the November 2024 changes. The `/items` endpoint works fine for new apps.

### Endpoints NOT Affected (Still Available to New Apps) [CONFIRMED]

The following remain accessible in Development Mode without Extended Quota:

- `GET /v1/tracks/{id}` — single track metadata (name, artists, album, duration, popularity, explicit flag, preview URL)
- `GET /v1/tracks?ids=...` — batch track metadata (same fields as above, up to 50 tracks)
- `GET /v1/albums/{id}` — album metadata
- `GET /v1/albums/{id}/tracks` — tracks on an album
- `GET /v1/search` — search (tracks, artists, albums, playlists)
- `GET /v1/me` — current user profile
- `GET /v1/me/playlists` — user's playlists
- `GET /v1/playlists/{id}` — playlist metadata
- `GET /v1/playlists/{id}/items` — playlist tracks (the current non-deprecated endpoint)
- `GET /v1/me/tracks` — user's saved tracks
- `GET /v1/me/top/tracks` — user's top tracks (requires `user-top-read` scope)
- `GET /v1/me/top/artists` — user's top artists (requires `user-top-read` scope)
- Playback control endpoints (requires Premium + appropriate scopes)
- `GET /v1/artists/{id}` — single artist (200 response, but genres may be empty — see above)

---

## 2. Status of Specific Endpoints (As of Early 2026)

### `/v1/audio-features` (batch) — HTTP 403

[CONFIRMED] This endpoint is restricted to Extended Quota Mode apps. New apps in Development Mode receive 403 Forbidden. The batch form (`?ids=...`) and single form (`/{id}`) are both restricted.

The data returned by this endpoint (when accessible) includes:
- `acousticness`, `danceability`, `energy`, `instrumentalness`
- `liveness`, `loudness`, `speechiness`, `valence`, `tempo`
- `key`, `mode`, `time_signature`
- `duration_ms`, `id`, `uri`, `type`

These were particularly valuable for music analysis and recommendation apps. Their restriction is the most impactful change for developers building music discovery tools.

### `/v1/artists?ids=...` (batch) — HTTP 403

[CONFIRMED] Batch artist lookups are restricted to Extended Quota Mode. The batch endpoint returns 403 for Development Mode apps.

The data that would be returned (when accessible) includes:
- `id`, `name`, `uri`, `href`, `external_urls`
- `genres` (array of genre strings — this is the key field)
- `popularity` (0–100)
- `followers.total`
- `images`

### `/v1/artists/{id}` (single) — HTTP 200 but no genres

[COMMUNITY] This is the most nuanced of the affected endpoints. The single-artist endpoint returns HTTP 200 and most fields, but the `genres` array is consistently empty (`[]`) for Development Mode apps even when Spotify's own clients show genre data for the same artist.

This appears to be intentional server-side behaviour where genre data is stripped from responses for Development Mode tokens. It is not documented explicitly by Spotify, but is widely reproduced across developer forums (Reddit r/learnpython, Stack Overflow, Spotify Community forums) since late 2024.

**Implication:** You cannot reliably use `/v1/artists/{id}` to get artist genres for new apps, even though the endpoint doesn't return a 403.

### `/v1/playlists/{id}/tracks` — HTTP 403

[CONFIRMED] This is a deprecated endpoint. Spotify deprecated `/tracks` in favour of `/items` because the `/items` endpoint also returns episodes (podcasts), not just tracks. New apps should use `/v1/playlists/{id}/items` instead.

The 403 on this endpoint is from the deprecation, not from the November 2024 quota changes. It is a separate issue.

**Fix:** Use `/v1/playlists/{id}/items` — works fine for new apps without Extended Quota.

### `/v1/playlists/{id}/items` — HTTP 200 (working)

[CONFIRMED] This is the current canonical endpoint for playlist tracks/items. It works without Extended Quota. Responses include track metadata (name, artists, album, duration, popularity) but not audio features.

---

## 3. Quota Extension / Extended Access Process

### What Is Extended Quota Mode? [CONFIRMED]

Extended Quota Mode (sometimes referred to in community discussions as "quota extension" or "extended access") is Spotify's approval process for apps that need access to restricted endpoints and/or more than 25 users.

### How to Apply [CONFIRMED]

1. Log in to the **Spotify Developer Dashboard** at `https://developer.spotify.com/dashboard`
2. Select your app
3. Navigate to **Settings** → **Request Extended Quota** (or similar — the exact UI label has changed slightly over time)
4. Fill out the application form which asks:
   - App description and use case
   - Which restricted endpoints you need and why
   - How you will handle user data and comply with Spotify's terms
   - Expected number of users
   - Whether the app is commercial or non-commercial

### Criteria for Approval [CONFIRMED / COMMUNITY]

Spotify has not published a precise checklist, but the following factors are widely understood to influence approval:

- **Legitimate consumer-facing use case** — personal tools or research projects have lower chances than polished consumer apps
- **Not competing with Spotify's core features** — apps that replicate Spotify's own recommendation or analysis features are less likely to be approved
- **Data handling compliance** — clear privacy policy, GDPR compliance where applicable
- **Not using data to train AI/ML models** — this is the primary concern Spotify cited in the November 2024 announcement
- **App completeness** — a live, functional app is more convincing than a prototype
- **Non-commercial personal tools** — reportedly have low approval rates; Spotify appears to prioritise commercial apps with clear revenue models

### Approval Timeline [COMMUNITY]

- Spotify does not publish SLA for review
- Community reports range from **2–8 weeks** for straightforward cases
- Some developers report receiving no response or receiving automatic rejections within days
- Appeals are possible but add further time
- As of early 2026, developers continue to report slow or unsuccessful approval processes for non-commercial or personal-use apps

### Important Caveats [CONFIRMED]

- Even with Extended Quota Mode, apps must not exceed Spotify's rate limits
- Apps approved for Extended Quota are subject to periodic review
- Spotify can revoke access if Terms of Service are violated
- The 25-user limit in Development Mode applies to users authorised via OAuth — it does not affect server-to-server (Client Credentials) calls, but those calls cannot access user-specific data

---

## 4. Alternative Sources for Audio Features and Artist Genres

### 4.1 Last.fm API

**URL:** `https://www.last.fm/api`
**Status:** [CONFIRMED] Active and freely available as of 2026

**What it provides:**
- **Artist tags** — community-sourced genre/mood tags for artists (e.g., "indie rock", "melancholic", "90s")
- **Track tags** — tags applied to specific tracks
- **Similar artists** — based on listener overlap
- **Track/artist/album metadata** — play counts, listener counts, wiki summaries
- **User listening history** — if integrated with scrobbling

**Key endpoint for genres:**
```
GET http://ws.audioscrobbler.com/2.0/?method=artist.gettoptags&artist={name}&api_key={key}
GET http://ws.audioscrobbler.com/2.0/?method=track.gettoptags&artist={artist}&track={track}&api_key={key}
```

**Auth:** API key only (no OAuth needed for read operations). Free to obtain.

**Rate limits:** [COMMUNITY] Approximately 5 requests/second for free tier; no officially published hard limit. Heavy usage may trigger throttling.

**Quality of genre data:** Tags are community-sourced and can be noisy (meme tags, very broad tags), but for popular artists the top 3–5 tags are generally reliable genre indicators. Less reliable for obscure artists.

**Free tier:** Yes — API key registration is free with no per-call cost.

**Recommendation:** Good first-pass source for artist genre tags. Combine top tags with a normalisation/filtering step to reduce noise.

---

### 4.2 MusicBrainz API

**URL:** `https://musicbrainz.org/doc/MusicBrainz_API`
**Status:** [CONFIRMED] Active and freely available as of 2026

**What it provides:**
- **Artist genres** — via the `genres` field (requires `inc=genres` parameter)
- **Recording (track) metadata** — title, artist credits, duration, ISRCs
- **Release (album) metadata** — label, country, date, track listing
- **Artist metadata** — type, area, life-span
- **Relationships** — between artists, recordings, releases

**Key endpoints for genres:**
```
GET https://musicbrainz.org/ws/2/artist/{mbid}?inc=genres&fmt=json
GET https://musicbrainz.org/ws/2/artist?query={name}&inc=genres&fmt=json
```

**Auth:** No auth required for read-only access. User-Agent header strongly recommended (required by their policy):
```
User-Agent: YourAppName/1.0 (your@email.com)
```

**Rate limits:** [CONFIRMED] **1 request/second** for unauthenticated requests. This is strictly enforced and violations result in IP bans. With a MusicBrainz account (free), the limit is still 1 req/sec. MusicBrainz explicitly asks developers to cache aggressively and not hammer their servers.

**Genre data quality:** MusicBrainz uses a curated, votable genre system. Data quality is high for well-known artists but coverage of niche or very new artists can be sparse. Genres are more standardised than Last.fm tags.

**Lookup strategy:** You typically need to resolve a Spotify artist name or MBID (MusicBrainz ID) first. Spotify's own API used to return `external_ids.musicbrainz` but this is unreliable. A fuzzy name search against MusicBrainz is usually needed.

**Free tier:** Fully free. MusicBrainz is a non-profit project.

**Recommendation:** Excellent for reliable, curated genre data, but the 1 req/sec rate limit makes it unsuitable for bulk lookups without significant caching. Best used as a supplementary enrichment source.

---

### 4.3 AcousticBrainz

**Status:** [CONFIRMED] **SHUT DOWN on 17 November 2022.**

AcousticBrainz was a community-driven project hosted by the MetaBrainz Foundation that provided audio features (tempo, key, mood, danceability, etc.) for millions of tracks, extracted using the Essentia audio analysis library.

The project was officially discontinued in November 2022 due to lack of funding and maintenance capacity. The website is no longer accessible. A final data dump was made available for researchers before shutdown.

**What this means:** AcousticBrainz cannot be used as a live API source. The final dataset snapshot may be available via MetaBrainz/Internet Archive for offline use in research contexts.

---

### 4.4 Essentia (Open Source Audio Analysis)

**URL:** `https://essentia.upf.edu/`
**Status:** [CONFIRMED] Active open-source project maintained by the Music Technology Group at Universitat Pompeu Fabra (Barcelona)

**What it provides:**
- Full audio analysis: tempo/BPM, key, mode, loudness, danceability, energy
- Mood/emotion classification (happy, sad, aggressive, relaxed, etc.)
- Instrument detection, vocal detection
- Genre classification (using pre-trained models)
- Beat tracking, onset detection, chord detection

**How it works:** Essentia is a C++ library with Python bindings. It runs locally on audio files — it does **not** use an API. You must provide the actual audio data (MP3, WAV, FLAC, etc.).

**The critical limitation:** To analyse tracks using Essentia, you need the actual audio files. Spotify does not provide audio file access via its API. Preview URLs (30-second MP3 clips) used to be available but Spotify deprecated `preview_url` for many tracks. Even if preview URLs are available, 30 seconds may not be sufficient for reliable analysis.

**Pre-trained models:** Essentia provides pre-trained TensorFlow/TorchScript models for genre, mood, key, BPM, danceability, and more. These are available at `https://essentia.upf.edu/models.html`.

**Recommendation:** Excellent for offline batch analysis if you have audio files. Not viable as a drop-in replacement for the Spotify Audio Features API when you only have track metadata (no audio files).

---

### 4.5 Other Sources Considered

#### Musicovery / Tunebat / Similar Services
Several commercial services offer audio feature data (BPM, key, energy) via their own APIs. As of early 2026:
- **Tunebat** — provides BPM/key lookup via web UI; no documented public API
- **GetSongBPM** — similar, no public API
- These are not viable programmatic alternatives

#### Discogs API
- `https://www.discogs.com/developers`
- Provides release/artist metadata and genre/style tags
- Genres are coarser than Spotify (e.g., "Electronic", "Rock") with sub-genre "styles" (e.g., "House", "Techno")
- Rate limits: 60 requests/min unauthenticated, 240/min with OAuth token
- Useful supplement for genre data, particularly for electronic music and vinyl-centric genres
- Coverage is strongest for physical releases (vinyl, CD); streaming-only releases may be missing

#### Wikidata / Wikipedia
- Artist genre data exists in Wikidata and can be queried via SPARQL
- Quality varies widely; coverage is good for mainstream artists
- Not practical for automated bulk lookups at scale

---

## 5. Artist Genres: Is Any Spotify Endpoint Still Returning Genre Data?

### Short Answer: No, Not Reliably for New Apps

[COMMUNITY] Based on extensive developer reports and testing as of late 2024/early 2025:

| Endpoint | Status | Genres Returned? |
|----------|--------|-----------------|
| `GET /v1/artists/{id}` | HTTP 200 | `genres: []` (empty array) |
| `GET /v1/artists?ids=...` | HTTP 403 | N/A |
| `GET /v1/me/top/artists` | HTTP 200 | `genres: []` (empty array) |
| `GET /v1/search?type=artist` | HTTP 200 | `genres: []` (empty array) |

The `genres` field on artist objects across all endpoints appears to be silently suppressed for Development Mode apps. This is not documented by Spotify but is consistently reproduced.

**Note on `GET /v1/me/top/artists`:** This endpoint, which returns the current user's top artists, was previously a workaround because it returned artist objects with genres. As of late 2024, it also returns empty genre arrays for Development Mode apps.

### Workaround via Related Artists
`GET /v1/artists/{id}/related-artists` — [UNCONFIRMED as of research date] This endpoint's status for Development Mode is unclear. It may return artist objects with empty genre arrays.

---

## 6. What Data IS Available from Spotify for New Apps (Without Extended Access)

### Track Data (via `/v1/tracks`)
```json
{
  "id": "...",
  "name": "Track Name",
  "artists": [{"id": "...", "name": "Artist Name"}],
  "album": {
    "id": "...",
    "name": "Album Name",
    "release_date": "2024-01-15",
    "images": [...]
  },
  "duration_ms": 210000,
  "popularity": 72,
  "explicit": false,
  "preview_url": "..." ,  // may be null — increasingly deprecated
  "track_number": 3,
  "disc_number": 1,
  "is_local": false,
  "external_ids": {"isrc": "USRC12345678"},
  "external_urls": {"spotify": "https://open.spotify.com/track/..."}
}
```

**NOT available:** `audio_features` (tempo, key, energy, valence, danceability, etc.)

### Artist Data (via `/v1/artists/{id}`)
```json
{
  "id": "...",
  "name": "Artist Name",
  "popularity": 68,
  "followers": {"total": 1234567},
  "images": [...],
  "genres": [],  // ALWAYS EMPTY for Development Mode apps
  "external_urls": {"spotify": "..."},
  "uri": "spotify:artist:..."
}
```

### Album Data (via `/v1/albums/{id}`)
```json
{
  "id": "...",
  "name": "Album Name",
  "album_type": "album",
  "release_date": "2024-01-15",
  "total_tracks": 12,
  "artists": [...],
  "tracks": {...},
  "popularity": 65,
  "genres": [],  // Also empty on album objects
  "label": "Label Name",
  "copyrights": [...]
}
```

### User Data (via `/v1/me`)
- Display name, email, country, product (free/premium), followers, profile image

### Playlist Data (via `/v1/playlists/{id}/items`)
- Full track metadata for each item (same as track data above)
- Playlist name, description, owner, follower count, images

### User Listening History
- `GET /v1/me/top/tracks` — user's top tracks (medium/long/short term)
- `GET /v1/me/top/artists` — user's top artists (genres empty)
- `GET /v1/me/player/recently-played` — last 50 recently played tracks
- `GET /v1/me/tracks` — user's saved/liked tracks

---

## 7. Workarounds and Community Solutions

### 7.1 Last.fm Tag Lookup for Genres (Most Practical)

The most commonly adopted workaround for artist genres is querying Last.fm's `artist.getTopTags` endpoint.

**Approach:**
1. From the Spotify artist object, get the artist name
2. Query Last.fm: `artist.getTopTags&artist={name}`
3. Filter the returned tags by count (e.g., only use tags with count > 50) to reduce noise
4. Optionally normalise tags against a known genre taxonomy

**Limitations:**
- Name matching can fail for artists with common names or name variants
- Less reliable for artists with few Last.fm listeners
- Tags are folksonomy, not a controlled vocabulary

**Example Last.fm response (artist.getTopTags):**
```json
{
  "toptags": {
    "tag": [
      {"name": "indie rock", "count": 100, "url": "..."},
      {"name": "alternative", "count": 87, "url": "..."},
      {"name": "indie", "count": 76, "url": "..."}
    ]
  }
}
```

### 7.2 Scraping Spotify's Public Web Pages (Not Recommended)

Some developers scrape `https://open.spotify.com/artist/{id}` which renders genre data in its HTML/JSON-LD. This approach:
- Violates Spotify's Terms of Service
- Is fragile (page structure changes frequently)
- Is not suitable for production use
- May result in IP bans

**Not recommended.**

### 7.3 Using Spotify's iOS/Android App Client Secrets (Not Recommended)

Some tools (e.g., Spotipy workarounds, certain open-source projects) attempt to use Spotify's internal app client IDs/secrets to bypass restrictions. This:
- Violates Spotify's Terms of Service
- Is legally risky
- Credentials are rotated by Spotify when discovered

**Not recommended.**

### 7.4 Applying for Extended Quota Mode

For legitimate apps, the correct path is to apply for Extended Quota Mode through the Developer Dashboard. See Section 3 for details.

### 7.5 Caching + Seeding from Extended-Access Apps

[COMMUNITY] Some developers maintain a second "extended access" app that they use internally to pre-cache audio features and genres into their own database, then serve that cached data to their production app. This is:
- Only feasible if you already have Extended Quota Mode on at least one app
- Borderline in terms of ToS compliance (Spotify's ToS restricts commercial redistribution of their data)
- Not a scalable solution for new developers starting from scratch

### 7.6 Open Source Dataset Approach

For offline or research use, the following datasets may be useful:

- **Million Song Dataset (MSD):** ~1M songs with audio features extracted from proprietary analysis (Echo Nest, later acquired by Spotify). Available via Columbia University / Internet Archive. Old (2011) but large.
- **Free Music Archive (FMA):** ~100K tracks with Librosa-extracted features. [CONFIRMED] Available at `https://github.com/mdeff/fma`
- **Spotify Kaggle Datasets:** Various community datasets on Kaggle with audio features that were scraped before the November 2024 restrictions. Useful for historical data; will not have recent tracks.

### 7.7 BPM/Key from Audio Preview URLs (Limited)

If Spotify preview URLs are available (30-second MP3 clips), you could run local analysis using Librosa (Python) or Essentia to extract:
- BPM / tempo
- Key and mode
- Approximate energy / loudness

**Limitations:**
- `preview_url` is increasingly null for tracks (Spotify has been rolling back previews for several years)
- 30 seconds is insufficient for reliable analysis of all features
- Requires downloading audio and running analysis (compute cost)
- Does not solve the genres problem

**Librosa example:**
```python
import librosa
y, sr = librosa.load('preview.mp3')
tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
```

---

## 8. Summary and Recommendations

### Current Situation (Early 2026)

| Need | Solution |
|------|----------|
| Artist genres | Last.fm `artist.getTopTags` (primary), MusicBrainz `artist?inc=genres` (secondary/fallback) |
| Audio features (tempo, key, energy, etc.) | No free live alternative. Options: apply for Extended Quota, use Librosa on preview audio if available, use historical datasets |
| Batch artist lookup | Apply for Extended Quota Mode, or loop single-artist calls with caching |
| Playlist tracks | Use `/v1/playlists/{id}/items` (works fine) |
| Track metadata (name, artist, album, duration, popularity) | Available from Spotify without Extended Quota |
| BPM/tempo specifically | GetSongBPM web lookup (manual/scraping), Librosa on audio, or historical datasets |

### Recommended Architecture for a New App (Without Extended Quota)

1. **Fetch track metadata** from Spotify (`/v1/tracks`, `/v1/playlists/{id}/items`) — fully available
2. **Fetch artist names** from Spotify artist objects in track responses
3. **Look up genres** via Last.fm `artist.getTopTags` — cache results aggressively
4. **Supplement genres** with MusicBrainz for artists where Last.fm data is poor — respect 1 req/sec limit
5. **Apply for Extended Quota Mode** if audio features are essential to the app's core function — frame the use case clearly and demonstrate the app is live and user-facing

### Key URLs for Further Reference

| Resource | URL |
|----------|-----|
| Spotify November 2024 announcement | `https://developer.spotify.com/blog/2024-11-27-changes-to-the-web-api` |
| Spotify Developer Dashboard | `https://developer.spotify.com/dashboard` |
| Spotify quota modes docs | `https://developer.spotify.com/documentation/web-api/concepts/quota-modes` |
| Spotify API reference | `https://developer.spotify.com/documentation/web-api/reference` |
| Last.fm API | `https://www.last.fm/api` |
| Last.fm artist.getTopTags | `https://www.last.fm/api/show/artist.getTopTags` |
| MusicBrainz API docs | `https://musicbrainz.org/doc/MusicBrainz_API` |
| Essentia | `https://essentia.upf.edu/` |
| Essentia pre-trained models | `https://essentia.upf.edu/models.html` |
| Free Music Archive dataset | `https://github.com/mdeff/fma` |
| Spotify Community forums | `https://community.spotify.com/t5/Spotify-for-Developers/bd-p/Spotify_Developer` |

---

## 9. Confidence Assessment

| Claim | Confidence |
|-------|-----------|
| November 2024 blog post date and URL | HIGH — widely cited across developer community |
| `/v1/audio-features` returns 403 for new apps | HIGH — confirmed by OP's own testing and widespread community reports |
| `/v1/artists?ids=...` returns 403 for new apps | HIGH — confirmed by OP's own testing |
| `/v1/artists/{id}` returns 200 but empty genres | HIGH — community-confirmed pattern |
| Extended Quota application process via dashboard | HIGH — documented in Spotify developer docs |
| Extended Quota approval timeline (2–8 weeks) | MEDIUM — based on community reports, not official SLA |
| Last.fm API capabilities and rate limits | HIGH — well-documented |
| MusicBrainz 1 req/sec rate limit | HIGH — documented on MusicBrainz wiki |
| AcousticBrainz shutdown date (Nov 2022) | HIGH — official MetaBrainz announcement |
| `preview_url` increasingly null | MEDIUM — widely reported but not officially documented as a policy |

---

*Document compiled February 2026. API behaviour can change without notice. Verify against current Spotify documentation and test against live endpoints.*
