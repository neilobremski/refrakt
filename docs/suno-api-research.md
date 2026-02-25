# Suno AI API Research

**Research date:** February 24, 2026
**Compiled by:** Claude Code (knowledge cutoff: August 2025)
**Live verification:** February 24, 2026 — actual API calls made against a real Suno Pro account confirmed several facts. See Section 0 below.
**Web research note:** Network fetch tools (WebFetch, curl, git clone) were unavailable during the live research session on Feb 24 2026. Web-sourced findings (gcui-art repo status, official API announcements) could not be independently retrieved. The live verification results in Section 0 are from direct API testing and are authoritative.

---

## Table of Contents

0. [LIVE VERIFICATION RESULTS (Feb 24 2026)](#0-live-verification-results-feb-24-2026)
1. [Official API Status](#1-official-api-status)
2. [gcui-art/suno-api — Reverse-Engineered Wrapper](#2-gcui-artsuno-api--reverse-engineered-wrapper)
3. [Suno Web App Network Traffic and Endpoints](#3-suno-web-app-network-traffic-and-endpoints)
4. [Terms of Service Implications](#4-terms-of-service-implications)
5. [Output Formats and Quality](#5-output-formats-and-quality)
6. [Prompt Structure and Style Tags](#6-prompt-structure-and-style-tags)
7. [Other Community Tools and Wrappers](#7-other-community-tools-and-wrappers)
8. [Practical Limitations: Credits, Queue, Generation Time](#8-practical-limitations-credits-queue-generation-time)
9. [Summary and Recommended Approach](#9-summary-and-recommended-approach)
10. [References and URLs to Verify](#10-references-and-urls-to-verify)

---

## 0. LIVE VERIFICATION RESULTS (Feb 24 2026)

**Source:** Direct API calls against a real Suno Pro account on February 24, 2026. These results supersede all [VERIFY] items in the document that they address.

### Summary of confirmed facts

The following were confirmed by actually calling the API (not inferred from training data):

| # | Finding | Old doc said | Confirmed reality |
|---|---------|--------------|-------------------|
| 1 | Auth domain | `clerk.suno.com` | **`auth.suno.com`** |
| 2 | API base domain | `studio-api.suno.ai` | **`studio-api.prod.suno.com`** |
| 3 | JWT refresh endpoint | `POST clerk.suno.com/v1/client/sessions/{id}/tokens` | **`POST auth.suno.com/v1/client/sessions/{id}/tokens`** with `Cookie: __client={long_lived_token}` and `Origin: https://suno.com` header required |
| 4 | Generate endpoint path | `/api/generate/v2/` | **`/api/generate/v2-web/`** (note `-web` suffix) |
| 5 | hCaptcha requirement | Not mentioned | **REQUIRED** — every generate request needs `"token": "P1_..."` hCaptcha response in JSON body; without it → HTTP 422 "Token validation failed" |
| 6 | Current model name | `chirp-v4` listed as latest | **`chirp-crow`** = v5 (current default as of Feb 2026) |
| 7 | Poll endpoint | `GET studio-api.suno.ai/api/feed/?ids=...` | **`GET studio-api.prod.suno.com/api/feed/?ids={clip_ids}`** — confirmed working with `Authorization: Bearer {JWT}` + `Cookie: sessionid={django_session}` |
| 8 | Audio CDN | S3 signed URLs (guessed) | **`https://cdn1.suno.ai/{clip_id}.mp3`** — publicly accessible once complete; no signed URL expiry |
| 9 | Credit cost | 10 credits per song (2 clips) | **Confirmed: 10 credits per generation** (2 clips). Pro = 2,500 credits/month; 2,480 remaining after 2 test generations |
| 10 | MP3 quality | 128 kbps, 44.1 kHz stereo | **64 kbps, 48 kHz stereo** (lower bitrate and different sample rate than documented) |

### Critical new finding: hCaptcha is a major barrier

**This is the single most important discovery.** Every call to the generate endpoint requires a valid hCaptcha token in the request body:

```json
{
  "token": "P1_eyJ0eXAiOiJKV1QiLCJhbGci...",
  ...other fields...
}
```

Without this token, the API returns HTTP 422 with body `"Token validation failed"`. This means:

- The gcui-art/suno-api wrapper (and any similar tool that does not solve hCaptcha) will fail at the generate step.
- Any automated pipeline must either:
  1. Integrate an hCaptcha solver service (e.g., 2captcha, CapSolver, Anti-Captcha) — costs ~$1–3 per 1,000 solves
  2. Find a way to bypass or mock the captcha (may violate hCaptcha ToS and Suno ToS)
  3. Accept manual intervention for each generation batch
- This requirement was **not documented** in the gcui-art/suno-api README as of the training cutoff (August 2025), suggesting it was added after that date.

### Auth flow — confirmed working pattern

```
1. Long-lived token:  __client cookie from browser (Clerk session)
2. JWT refresh:       POST https://auth.suno.com/v1/client/sessions/{session_id}/tokens
                      Headers: Cookie: __client={value}, Origin: https://suno.com
                      Response: { "jwt": "eyJ..." }  (expires ~60s)
3. Django session:    sessionid cookie — also required on poll calls
4. Generate call:     POST https://studio-api.prod.suno.com/api/generate/v2-web/
                      Headers: Authorization: Bearer {jwt}, Cookie: sessionid={value}
                      Body: { ..., "token": "{hcaptcha_token}", "mv": "chirp-crow" }
5. Poll:              GET https://studio-api.prod.suno.com/api/feed/?ids={clip_ids}
                      Headers: Authorization: Bearer {jwt}, Cookie: sessionid={django_session}
6. Download:          GET https://cdn1.suno.ai/{clip_id}.mp3  (public, no auth needed)
```

### Web research status (Feb 24 2026)

Network fetch tools (WebFetch, curl, git clone) were not available during this research session. The following items **remain unverified by live web fetch**:

- Whether Suno has launched an official public API (suno.com/developers)
- Current gcui-art/suno-api commit date, star count, and whether README has been updated for hCaptcha
- Python alternative wrappers post-August 2025

These items should be checked manually using a browser.

---

## 1. Official API Status

### Confirmed (as of knowledge cutoff, August 2025)

Suno AI did **not** have a publicly accessible, documented API as of August 2025. There was no official developer portal, API key system, or documented REST API endpoints published by Suno.

Suno's business model was subscription-based for consumers (free tier, Pro, Premier). There was no B2B API offering or "Suno for Developers" product announced publicly through mid-2025.

### What may have changed [VERIFY — web fetch unavailable Feb 24 2026]

- Suno has been one of the fastest-growing AI music tools. It is plausible that between August 2025 and February 2026, Suno launched or announced a developer API.
- Check: https://suno.com/developers (or /api, /docs) — these URLs were not live as of training cutoff but are the most likely candidates.
- Check: Suno's official blog at https://suno.com/blog for any "Introducing the Suno API" post.
- Check: Suno's Discord server (linked from their site) — often the first place API announcements reach developers.

### Confidence: High (no official API as of Aug 2025) / [VERIFY] Feb 2026 status — web fetch was unavailable

---

## 2. gcui-art/suno-api — Reverse-Engineered Wrapper

### Repository

- **GitHub URL:** https://github.com/gcui-art/suno-api
- **Language:** TypeScript / Node.js
- **Primary author / org:** gcui-art
- **License:** MIT

### What it is

`gcui-art/suno-api` is a reverse-engineered, self-hosted HTTP wrapper around Suno's internal web API. It impersonates a logged-in Suno browser session by reusing the session cookie that the Suno web app sends to its backend. You run it as a local Docker container or Node server, configure it with your Suno session cookie, and it exposes a clean REST API on localhost.

### Authentication approach (Cookie-based)

1. Log into Suno at https://suno.com using your browser.
2. Open DevTools → Application → Cookies → `suno.com`.
3. Copy the value of the `__client` cookie (Clerk authentication token) — this is the session token the web app uses for all API calls.
4. Set this as the `SUNO_COOKIE` environment variable when running the container.
5. The wrapper renews the cookie's JWT automatically by calling the auth token refresh endpoint periodically.

**CORRECTION (verified Feb 24 2026):** The auth domain is `auth.suno.com`, not `clerk.suno.com` as the gcui-art README previously stated. The JWT refresh call also requires an `Origin: https://suno.com` header.

**Important caveat:** This cookie is tied to your user session and expires. If you log out from the web interface, the cookie is invalidated. The tool typically refreshes the underlying JWT (which has a ~1 hour TTL) automatically in the background, but the session cookie itself needs periodic manual renewal (days to weeks depending on session lifetime).

### Endpoints exposed by gcui-art/suno-api

The wrapper exposes an OpenAI-compatible REST API on `http://localhost:3000` (configurable). As of the last known version (circa late 2024):

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/generate` | Generate music from a text prompt |
| POST | `/api/custom_generate` | Generate with explicit style tags, title, BPM, etc. |
| GET | `/api/get` | Poll status of a generation by clip IDs |
| GET | `/api/get_limit` | Fetch remaining credits for the authenticated account |
| GET | `/api/get_clip` | Fetch metadata for a single clip |
| POST | `/api/generate_lyrics` | Generate lyrics from a text prompt |
| GET | `/api/get_lyrics` | Poll status of a lyrics generation job |

The `generate` and `custom_generate` endpoints accept JSON bodies and return clip IDs. Because generation is async, callers must poll `/api/get` with those clip IDs until the `status` field reaches `"complete"`.

### Maintenance status and hCaptcha impact [VERIFY — web fetch unavailable Feb 24 2026]

- The repo was last observed to have significant activity in late 2024 (November 2024 per CLAUDE.md notes in this project).
- **Critical:** Our live testing on Feb 24 2026 confirmed that Suno now requires a valid hCaptcha token on every generate request. If gcui-art/suno-api has not been updated to solve hCaptcha, its `/api/generate` and `/api/custom_generate` endpoints will return errors (proxying the HTTP 422 from Suno). This is the most likely current failure mode.
- **Action:** Visit https://github.com/gcui-art/suno-api to check: last commit date, open issues mentioning "hcaptcha", "captcha", "422", "Token validation failed", and whether the README documents a captcha solution.
- Secondary failure mode: the auth domain changed from `clerk.suno.com` to `auth.suno.com` — check if the repo's JWT refresh code still uses the old domain.
- Secondary failure mode: the generate endpoint path changed from `/api/generate/v2/` to `/api/generate/v2-web/`.

### Deployment

The repo ships a `Dockerfile` and `docker-compose.yml`. Typical setup:

```bash
git clone https://github.com/gcui-art/suno-api
cd suno-api
# Edit .env or set SUNO_COOKIE env var
docker-compose up -d
# API is now available at http://localhost:3000
```

The `VERCEL_URL` environment variable can optionally be set for deployment to Vercel (the project supports serverless deployment).

### Confidence: High (accurate description of the tool's design) / [VERIFY] current maintenance, hCaptcha handling, and updated domains

---

## 3. Suno Web App Network Traffic and Endpoints

### Base API domain — CORRECTED

~~All Suno web app API calls go to `https://studio-api.suno.ai`~~

**CORRECTED (verified Feb 24 2026):** The API base domain is:

```
https://studio-api.prod.suno.com
```

The old `studio-api.suno.ai` domain appears to no longer be the active endpoint. All requests should use `studio-api.prod.suno.com`.

### Key internal endpoints — updated with verified values

These endpoints were confirmed via direct API calls on February 24, 2026:

#### Authentication / Session

- `POST https://auth.suno.com/v1/client/sessions/{session_id}/tokens`
  - **Required headers:** `Cookie: __client={long_lived_token}`, `Origin: https://suno.com`
  - **Response:** `{ "jwt": "eyJ..." }` — token expires approximately 60 seconds after issuance
  - **OLD (incorrect):** `POST https://clerk.suno.com/v1/client/sessions/{session_id}/tokens`

The JWT is passed as:
```
Authorization: Bearer <jwt>
```
on all calls to `studio-api.prod.suno.com`.

Additionally, a `sessionid` Django session cookie is also required on poll calls:
```
Cookie: sessionid=<django_session_value>
```

#### Music Generation — CORRECTED

```
POST https://studio-api.prod.suno.com/api/generate/v2-web/
```

**Note the `-web` suffix** — the old `/v2/` path no longer works (returns 422).

Required headers:
```
Authorization: Bearer <jwt>
Cookie: sessionid=<django_session>
Content-Type: application/json
```

Request body (JSON) — **hCaptcha token is required**:
```json
{
  "gpt_description_prompt": "ambient piano, melancholic, slow tempo",
  "make_instrumental": true,
  "mv": "chirp-crow",
  "prompt": "",
  "generation_type": "TEXT",
  "token": "P1_eyJ0eXAi..."
}
```

Or for custom mode (explicit style + lyrics):
```json
{
  "title": "My Track Title",
  "tags": "ambient piano, melancholic, slow tempo, instrumental",
  "prompt": "[Verse]\n...",
  "make_instrumental": false,
  "mv": "chirp-crow",
  "generation_type": "TEXT",
  "token": "P1_eyJ0eXAi..."
}
```

**`"token"` is mandatory.** Omitting it returns HTTP 422 `"Token validation failed"`.

Response: returns two clip objects (Suno always generates in pairs), each with a unique clip ID (UUID string) and initial status `"submitted"` or `"queued"`.

#### Polling for completion — CORRECTED domain

```
GET https://studio-api.prod.suno.com/api/feed/?ids={clip_id1},{clip_id2}
```

Confirmed working on Feb 24 2026 with `Authorization: Bearer {JWT}` + `Cookie: sessionid={django_session}`.

Returns an array of clip objects. Poll until `status == "complete"`. Typical polling interval: 5 seconds. The `audio_url` field is populated on completion.

#### Audio download — CDN confirmed

```
GET https://cdn1.suno.ai/{clip_id}.mp3
```

Confirmed Feb 24 2026: publicly accessible once generation is complete; no authentication or signed URL required. Audio is persistently available (not time-limited as previously guessed).

#### Credits / Quota — domain corrected

```
GET https://studio-api.prod.suno.com/api/billing/info/
```

#### Feed / History — domain corrected

```
GET https://studio-api.prod.suno.com/api/feed/
GET https://studio-api.prod.suno.com/api/feed/?page=0
```

#### Lyrics Generation — domain corrected

```
POST https://studio-api.prod.suno.com/api/generate/lyrics/
```

Returns a job ID; poll with:
```
GET https://studio-api.prod.suno.com/api/generate/lyrics/{job_id}
```

### Model versions — UPDATED

The `mv` field controls which Suno model is used. Updated table:

| Value | Description | Status |
|-------|-------------|--------|
| `chirp-v3` | Suno v3 (released ~early 2024) | Legacy |
| `chirp-v3-5` | Suno v3.5 (released ~mid-2024) | Legacy |
| `chirp-v4` | Suno v4 (released ~late 2024) | Legacy |
| `chirp-crow` | Suno v5 (confirmed current as of Feb 24 2026) | **Current default** |

**CORRECTION:** The document previously listed `chirp-v4` as the latest model. As of February 24, 2026 (confirmed via live API call), the current model is `chirp-crow` which corresponds to Suno v5.

### Confidence: All corrected values are CONFIRMED by live API testing on Feb 24 2026

---

## 4. Terms of Service Implications

### What Suno's ToS says about automated access

As of mid-2025, Suno's Terms of Service (https://suno.com/terms) included clauses that:

1. **Prohibit unauthorized automated access:** The ToS explicitly prohibits using "bots, scripts, or automated means" to access the service without express written permission.
2. **Prohibit reverse engineering:** The ToS prohibits reverse engineering, decompiling, or attempting to extract source code or underlying APIs.
3. **Account termination risk:** Violation of these terms can result in immediate account suspension or termination without notice.
4. **Commercial use of generated content:** Suno's terms around ownership and commercial use vary by subscription tier — free tier users have limited commercial rights; Pro/Premier subscribers have broader rights. This is separate from the API access question.

### Risk assessment for cookie-based unofficial access

| Risk | Level | Notes |
|------|-------|-------|
| Account ban | Medium-High | Automated generation is detectable via usage patterns |
| Legal exposure | Low-Medium | ToS violation is a contractual matter, not criminal; Suno has not pursued legal action against individual users to date (as of training cutoff) |
| API breakage | High | Suno changes internal APIs frequently; any unofficial tool can stop working at any time |
| Rate limiting / blocking | Medium | Suno may block IPs or sessions exhibiting bot-like patterns |

### Updated risk: hCaptcha

The addition of hCaptcha to the generate endpoint (confirmed Feb 24 2026) adds a new practical barrier:

- Using a third-party CAPTCHA-solving service to bypass hCaptcha likely violates both Suno's ToS and hCaptcha's own terms of service.
- This increases the effective complexity and cost of automation.
- It also signals that Suno is actively working to prevent automated/bot access.

### Practical considerations

- Using a **dedicated Suno account** for automation (not your primary personal account) reduces the risk of losing valued content if the account is suspended.
- Generating a small, reasonable volume of tracks is less likely to trigger automated detection than bulk generation.
- Checking whether Suno has launched an **official partnership or API program** by February 2026 is the most important first step — using official channels eliminates all ToS risk.

### Confidence: High (ToS content well-documented) / [VERIFY] whether terms have changed and whether an official API path now exists

---

## 5. Output Formats and Quality

### Audio Format — CORRECTED

Suno outputs audio in **MP3 format** for standard generation.

~~- **Bitrate:** 128 kbps MP3~~
~~- **Sample rate:** 44.1 kHz~~

**CORRECTED (confirmed via live download, Feb 24 2026):**
- **Bitrate:** **64 kbps** MP3
- **Sample rate:** **48 kHz**
- **Channels:** Stereo

The audio quality is lower than previously documented. At 64 kbps, the output is acceptable for web streaming / background music but is not CD quality. This may affect downstream processing (stem separation, mastering) that benefits from higher source quality.

[VERIFY] Whether higher quality / lossless formats (WAV, FLAC, 128+ kbps MP3) are available on Premier tier as of early 2026. This was not confirmed in our Feb 24 2026 testing (which used a Pro account).

### Video Format

Suno also generates a short looping animated video (music video) for each track, available as MP4. This is used for the in-app visual display and shareable clips, but is less relevant for audio-only pipelines.

### Image Format

Album art / cover image for each clip is provided as a JPG URL via the `image_url` field in clip metadata.

### Duration

- Standard generation: Suno generates clips of approximately **1 minute 20 seconds to 2 minutes** per generation.
- **Continue / Extend:** The web UI supports "extending" a clip to continue the song; this can produce longer pieces. Whether the unofficial API supports extend is [VERIFY] — it was a feature in some versions of gcui-art/suno-api via a `/api/concat` or extend endpoint.
- **Full song mode:** Suno v3.5+ supports generating longer tracks (up to ~4 minutes) by internally stitching sections. [VERIFY] availability and API parameter for v5 / chirp-crow.

### Confidence: Bitrate/sample rate CONFIRMED via live download Feb 24 2026. Duration and extended format remain from training data.

---

## 6. Prompt Structure and Style Tags

### Two modes: Description mode vs. Custom mode

#### Mode 1: Description/GPT mode (simple)

Pass a free-text description to `gpt_description_prompt`. Suno's backend uses an LLM to translate this into actual style tags and generate the music. Best for natural language input.

```
"gpt_description_prompt": "a slow ambient instrumental with piano and soft strings, melancholic mood"
```

Suno will choose the genre tags and style attributes automatically.

#### Mode 2: Custom mode (explicit tags)

Pass explicit comma-separated style tags to the `tags` field, and optionally explicit lyrics to `prompt`.

```
"tags": "ambient, piano, strings, slow tempo, melancholic, atmospheric, reverb, instrumental"
```

This gives more precise control. The `prompt` field in custom mode is for **lyrics** (or `[Instrumental]` to suppress vocals). For instrumental tracks, either set `make_instrumental: true` or include `[Instrumental]` in the lyrics prompt field.

### Style tag vocabulary

Suno accepts a wide range of descriptors. These are not formally documented, but community testing has established the following categories:

#### Genre / Style
```
ambient, drone, post-rock, neo-classical, new age, lo-fi, jazz, blues, folk,
acoustic, electronic, downtempo, trip-hop, chillout, cinematic, orchestral,
chamber music, minimalist, progressive, psychedelic, indie, alternative
```

#### Instruments
```
piano, guitar, acoustic guitar, electric guitar, synthesizer, strings, violin,
cello, double bass, drums, percussion, flute, oboe, clarinet, trumpet, bass,
mellotron, rhodes, wurlitzer, vibraphone, marimba, harp
```

#### Mood / Emotion
```
melancholic, introspective, nostalgic, peaceful, calm, serene, contemplative,
uplifting, hopeful, bittersweet, tense, mysterious, dark, brooding, ethereal,
wistful, dreamy, euphoric, meditative, somber
```

#### Tempo / Energy
```
slow, very slow, mid-tempo, uptempo, fast, sparse, dense, minimalist,
low energy, high energy, [BPM: 70] (some versions accept explicit BPM notation)
```

#### Production / Texture
```
reverb, echo, delay, warm, lo-fi, tape saturation, analog, clean, lush,
layered, sparse, wide, intimate, distant, close-mic'd, atmospheric, spacious
```

#### Vocal directives (when not instrumental)
```
male vocals, female vocals, choir, harmonies, whispered, spoken word,
a cappella, no vocals, instrumental, wordless vocals, vocalise
```

### Prompt formatting conventions

- Tags are **comma-separated** with no special syntax needed for most descriptors.
- Order matters somewhat — earlier tags tend to carry more weight.
- Recommended tag count: **5–12 tags** for best results; too many tags can confuse the model.
- Avoid contradictory tags (e.g., "fast" and "slow tempo" together).
- For this project (ambient/instrumental), a typical effective prompt structure:

```
"ambient, [primary genre], [key instrument(s)], [mood 1], [mood 2], [tempo], instrumental, [texture/production notes]"
```

Example:
```
"ambient piano, neo-classical, melancholic, slow tempo, introspective, atmospheric, reverb, instrumental"
```

### Metatags / structural tags in lyrics field

When using custom mode with lyrics, Suno supports structural metatags in the lyrics `prompt` field:

```
[Verse]
[Chorus]
[Bridge]
[Outro]
[Intro]
[Pre-Chorus]
[Instrumental Break]
[Solo]
[Build]
[Drop]
```

For purely instrumental tracks, you can either:
- Use `make_instrumental: true` (API parameter), or
- Write only `[Instrumental]` in the prompt field.

### Confidence: High (prompt structure is well-documented by community)

---

## 7. Other Community Tools and Wrappers

### Active projects (as of training cutoff, mid-2025)

#### 1. gcui-art/suno-api (primary)
- **URL:** https://github.com/gcui-art/suno-api
- **Language:** TypeScript / Node.js
- **Approach:** Docker/local server, cookie auth
- **Stars:** ~4,000–5,000 (as of mid-2024; may have grown significantly)
- **Current status [VERIFY]:** Likely broken as of Feb 2026 due to: (a) hCaptcha requirement on generate endpoint, (b) auth domain changed to `auth.suno.com`, (c) generate endpoint path changed to `/api/generate/v2-web/`. Check open issues for "hcaptcha", "422", "Token validation failed".

#### 2. Python-based wrappers

Several Python wrappers exist on GitHub and PyPI, built on top of the same internal API:

- **`SunoAI` on PyPI / GitHub** — various authors have published packages named `suno-api`, `sunoai`, or `suno-python`. Quality and maintenance vary significantly. Search PyPI for `suno` to find current options.
- These typically wrap the same backend endpoints with Python `requests` or `httpx`.
- **Status [VERIFY]:** All Python wrappers that were functional before the hCaptcha requirement was introduced will have the same breakage. Check for any wrappers that explicitly mention hCaptcha handling.

Updated Python wrapper pattern (reflecting confirmed domains and endpoints):

```python
import httpx

class SunoClient:
    AUTH_BASE = "https://auth.suno.com"          # CORRECTED from clerk.suno.com
    API_BASE = "https://studio-api.prod.suno.com"  # CORRECTED from studio-api.suno.ai

    def __init__(self, client_cookie: str, session_id: str, django_session: str):
        self.client_cookie = client_cookie
        self.session_id = session_id
        self.django_session = django_session
        self.jwt = None

    def refresh_token(self):
        """Refresh the short-lived JWT bearer token."""
        resp = httpx.post(
            f"{self.AUTH_BASE}/v1/client/sessions/{self.session_id}/tokens",
            headers={
                "Cookie": f"__client={self.client_cookie}",
                "Origin": "https://suno.com",  # REQUIRED
            },
        )
        resp.raise_for_status()
        self.jwt = resp.json()["jwt"]

    def generate(self, prompt: str, instrumental: bool = True, hcaptcha_token: str = ""):
        """Generate music. hcaptcha_token is REQUIRED — obtain from hCaptcha solver."""
        self.refresh_token()
        resp = httpx.post(
            f"{self.API_BASE}/api/generate/v2-web/",  # CORRECTED path
            headers={
                "Authorization": f"Bearer {self.jwt}",
                "Cookie": f"sessionid={self.django_session}",
            },
            json={
                "gpt_description_prompt": prompt,
                "make_instrumental": instrumental,
                "mv": "chirp-crow",     # CORRECTED: v5 model name
                "generation_type": "TEXT",
                "token": hcaptcha_token,  # REQUIRED — 422 without this
            }
        )
        return resp.json()
```

#### 3. n8n / Make / Zapier integrations

Community members have built n8n automation workflows that call the gcui-art/suno-api wrapper as part of broader automation pipelines. Search the n8n community forum for "Suno" to find workflow templates. These are likely broken for the same reasons as gcui-art/suno-api.

#### 4. LangChain / LlamaIndex tools

Some community contributors have wrapped Suno generation as a LangChain `Tool` for use in AI agent workflows. These are typically thin wrappers around the Python approaches above.

#### 5. RVC / post-processing pipelines

Various community setups use Suno for initial generation, then pipe the MP3 output through:
- **RVC (Retrieval-based Voice Conversion)** for vocal transformation
- **Demucs** for stem separation (isolating bass, drums, vocals, etc.)
- **iZotope / Audacity** scripts for mastering

These are downstream of Suno generation and don't affect the API approach.

### [VERIFY] Projects that may have emerged post-August 2025

- Check GitHub with search: `suno api` filtered by "Updated: 2025-2026"
- Specifically look for: any wrapper that mentions hCaptcha integration, captcha solving, or that post-dates the hCaptcha requirement
- Check npm registry: https://www.npmjs.com/search?q=suno
- Check PyPI: https://pypi.org/search/?q=suno

### Confidence: Medium (community project landscape changes rapidly; hCaptcha finding from Feb 24 2026 testing may have invalidated all pre-existing wrappers)

---

## 8. Practical Limitations: Credits, Queue, Generation Time

### Credits system — confirmed values

Suno uses a credit-based system where each generation consumes credits:

| Action | Credit cost |
|--------|------------|
| Generate 1 song (= 2 clips) | **10 credits (confirmed Feb 24 2026)** |
| Generate lyrics | Unclear / possibly free |
| Extend/continue a clip | 5–10 credits (varies) |

### Subscription tiers (as of mid-2025)

| Tier | Monthly credits | Cost | Commercial rights |
|------|----------------|------|-------------------|
| Free | 50 credits (5 songs) | $0 | Non-commercial only |
| Pro | 2,500 credits (250 songs) | ~$10/month | Commercial use allowed |
| Premier | 10,000 credits (1,000 songs) | ~$30/month | Commercial use allowed |

**Confirmed (Feb 24 2026):** Pro tier = 2,500 credits/month. After 2 test generations (20 credits), 2,480 credits remain. This confirms the 10 credits per generation figure.

[VERIFY] Exact pricing as of early 2026 — pricing has changed multiple times since Suno's launch.

For the "Wordless Work" pipeline project, the playlist likely has 20–50 tracks. At 10 credits per song, this would cost:
- 20 tracks = 200 credits = within Free tier (but only ~50 on free, so Pro is needed)
- 50 tracks = 500 credits = well within Pro tier

### Generation time

- **Typical generation time:** 20–40 seconds per clip pair (both clips generated together)
- **Queue wait time:** Varies by server load. During peak hours (US daytime), may be 30–90 seconds before generation even starts.
- **Total wall clock time:** Expect 1–3 minutes per song generation including polling.
- For a 30-track playlist: budget ~30–90 minutes of total generation time.

### Rate limiting

- Suno does not publish official rate limits for the web API.
- Community reports suggest generating more than ~5 songs in rapid succession (< 30 second intervals) can trigger temporary slowdowns or errors.
- Recommended approach: Add a 5–10 second sleep between generation requests when batching.
- Do not run multiple concurrent generation requests from the same account.

### Queue / async model

Generation is always asynchronous:
1. Submit generation → receive clip IDs immediately
2. Poll `https://studio-api.prod.suno.com/api/feed/?ids=...` every 5 seconds
3. After 20–60 seconds (typically), `status` changes to `"complete"` and audio URLs are populated
4. Download audio from `https://cdn1.suno.ai/{clip_id}.mp3` (public, no expiry)

**CORRECTED:** The CDN URLs are not time-limited signed URLs. They are permanent public URLs at `cdn1.suno.ai` (confirmed Feb 24 2026).

### Concurrent generation

- Each API call generates exactly **2 clips** (Suno always generates in pairs from the same prompt, giving you two variations).
- For a pipeline that needs one definitive track per source song, you'll need to either:
  - Pick one of the two clips automatically (e.g., by audio length or random selection)
  - Present both to a human for selection
  - Use some automated quality metric

### Confidence: Credits/CDN confirmed via live testing Feb 24 2026. Generation time from training data.

---

## 9. Summary and Recommended Approach

### Decision tree for implementation (updated Feb 24 2026)

```
1. CHECK: Does Suno now have an official API?
   → Visit https://suno.com/developers or https://suno.com/api
   → Search Suno's blog for API announcements
   → If YES: Use official API. Eliminates all ToS risk.

2. If no official API:
   → Check if gcui-art/suno-api is still maintained AND handles hCaptcha
     (last commit within ~3 months, issues mentioning hcaptcha solved)
   → If YES and working: Use gcui-art/suno-api Docker container
   → If NO or broken (likely — hCaptcha added, domains changed):
     Implement direct studio-api.prod.suno.com calls in Python
     using the confirmed endpoints from Section 0 and 3.

3. Either way:
   → Use a dedicated Suno account for automation
   → Generate at human-plausible volumes and speeds
   → Add sleep intervals between requests (5–10 seconds minimum)

4. CAPTCHA: You must solve hCaptcha for every generate call.
   → Option A: Integrate hCaptcha solver API (2captcha, CapSolver, Anti-Captcha)
     Cost: ~$1–3 per 1,000 solves; for ~30 tracks this is negligible
   → Option B: Manual intervention — generate in small supervised batches
   → Option C: Investigate whether the hCaptcha site key can be solved
     with a headless browser approach using Playwright/Puppeteer
```

### Recommended implementation for this project

Given this is a personal pipeline for ~30 tracks:

1. **Do not rely on gcui-art/suno-api** — it is almost certainly broken due to hCaptcha, domain changes, and endpoint path changes. Verify before using.
2. **Implement a minimal Python client** directly against `studio-api.prod.suno.com` — the endpoint structure is confirmed and simple.
3. The key engineering challenges are now:
   - **hCaptcha token acquisition** — the most significant new barrier
   - **JWT refresh** — bearer token expires ~60 seconds after issuance; must refresh before each call
   - **Django sessionid** — must also be included on poll calls alongside the Bearer JWT
4. Use `make_instrumental: true` and the custom tags mode for best control.
5. Model to use: `chirp-crow` (v5, current as of Feb 24 2026).
6. Audio quality: plan for **64 kbps, 48 kHz** source files; this is adequate for streaming but may limit downstream mastering options.

### Confirmed working auth pattern (Feb 24 2026)

```python
import httpx
import time

AUTH_BASE = "https://auth.suno.com"
API_BASE = "https://studio-api.prod.suno.com"
CDN_BASE = "https://cdn1.suno.ai"

def refresh_jwt(session_id: str, client_cookie: str) -> str:
    """Refresh the short-lived JWT bearer token using auth.suno.com."""
    resp = httpx.post(
        f"{AUTH_BASE}/v1/client/sessions/{session_id}/tokens",
        headers={
            "Cookie": f"__client={client_cookie}",
            "Origin": "https://suno.com",  # Required
        },
    )
    resp.raise_for_status()
    return resp.json()["jwt"]

def generate(jwt: str, django_session: str, prompt: str, hcaptcha_token: str) -> dict:
    """Submit a generation request. hcaptcha_token is mandatory."""
    resp = httpx.post(
        f"{API_BASE}/api/generate/v2-web/",
        headers={
            "Authorization": f"Bearer {jwt}",
            "Cookie": f"sessionid={django_session}",
        },
        json={
            "gpt_description_prompt": prompt,
            "make_instrumental": True,
            "mv": "chirp-crow",
            "generation_type": "TEXT",
            "token": hcaptcha_token,  # Mandatory — 422 without this
        }
    )
    resp.raise_for_status()
    return resp.json()

def poll_until_complete(jwt: str, django_session: str, clip_ids: list, interval: int = 5) -> list:
    """Poll until all clips have status 'complete'."""
    ids_param = ",".join(clip_ids)
    while True:
        resp = httpx.get(
            f"{API_BASE}/api/feed/?ids={ids_param}",
            headers={
                "Authorization": f"Bearer {jwt}",
                "Cookie": f"sessionid={django_session}",
            }
        )
        clips = resp.json()
        if all(c["status"] == "complete" for c in clips):
            return clips
        time.sleep(interval)

def download_mp3(clip_id: str, output_path: str) -> None:
    """Download completed clip. CDN is public — no auth needed."""
    resp = httpx.get(f"{CDN_BASE}/{clip_id}.mp3")
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        f.write(resp.content)
```

---

## 10. References and URLs to Verify

### Must-verify URLs (open these first) — updated priorities

| URL | What to check | Priority |
|-----|---------------|----------|
| https://suno.com/developers | Whether an official API portal now exists | HIGH |
| https://suno.com/blog | Recent announcements about API, pricing, ToS changes | HIGH |
| https://github.com/gcui-art/suno-api | Last commit date, issues mentioning "hcaptcha"/"422"/"Token validation failed", README for updated domains | HIGH |
| https://github.com/gcui-art/suno-api/issues | Search "hcaptcha", "captcha", "422", "broken", "v2-web" | HIGH |
| https://suno.com/terms | Current ToS language on automated access | MEDIUM |

### Secondary resources

| URL | What to check |
|-----|---------------|
| https://discord.gg/suno (or via suno.com) | Developer/API channels; hCaptcha workarounds; community fixes |
| https://pypi.org/search/?q=suno | Current Python packages; look for any mentioning hCaptcha |
| https://www.npmjs.com/search?q=suno | Current npm packages |
| https://github.com/search?q=suno+api&type=repositories&sort=updated | Recently updated GitHub projects |
| https://www.reddit.com/r/SunoAI/ | Community discussion on current API status, captcha workarounds |
| https://2captcha.com or https://capsolver.com | hCaptcha solving services; check support for Suno's hCaptcha site key |

### Key technical references from community research

- gcui-art/suno-api README (primary technical source for cookie auth and endpoints — but note: domains and paths are outdated as of Feb 24 2026)
- GitHub issue trackers on suno-api (for current breakage status, captcha issues)
- Suno Discord #developer or #api channels (if they exist)
- Browser DevTools network capture on studio-api.prod.suno.com (authoritative source for current endpoint structure)

---

## Appendix: What Changed Since Training Cutoff (Aug 2025)

The following changes were confirmed via live API testing on February 24, 2026. These represent substantive API changes that break tools and documentation written before the changes:

| Change | Impact |
|--------|--------|
| Auth domain: `clerk.suno.com` → `auth.suno.com` | JWT refresh calls fail with old domain |
| API base: `studio-api.suno.ai` → `studio-api.prod.suno.com` | All API calls fail with old domain |
| Generate path: `/api/generate/v2/` → `/api/generate/v2-web/` | Generate calls return 404/422 with old path |
| hCaptcha token now required in generate body | All existing wrappers likely broken; adds captcha-solving complexity |
| Model name: `chirp-v4` → `chirp-crow` (v5) | Using old model name may produce deprecated output or errors |
| Audio quality: 128 kbps 44.1 kHz → 64 kbps 48 kHz | Lower source quality than expected |
| CDN URLs: permanent public URLs (not signed/expiring) | Simpler download pattern than feared |
| `sessionid` Django cookie required alongside Bearer JWT on poll | Poll calls fail without this cookie |
| `Origin: https://suno.com` header required on JWT refresh | JWT refresh fails without Origin header |

---

*This document was originally compiled from AI training data (knowledge cutoff August 2025). Section 0 and all CORRECTED items reflect live API testing on February 24, 2026. Web-fetch-dependent items (official API status, gcui-art repo current state) remain unverified by live web access and are marked [VERIFY].*
