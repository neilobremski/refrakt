# Spotify API Setup for Refrakt

This guide documents how the Spotify Developer App was created for the Refrakt project, which reads playlist data (including audio features) to generate Suno AI music prompts.

---

## Prerequisites

- A Spotify account (free or premium)
- Access to [developer.spotify.com](https://developer.spotify.com)

---

## Step 1: Log in to Spotify for Developers

Navigate to `https://developer.spotify.com` and log in with your Spotify credentials.


---

## Step 2: Accept Developer Terms of Service

On first visit to the Dashboard, you will be presented with the **Spotify Developer Terms** (Version 10, effective 15 May 2025). Scroll through, check the acceptance checkbox, and click **Accept the terms**.


---

## Step 3: Open the Dashboard

After accepting terms, you land on the main Dashboard. Since no apps exist yet, it shows "You haven't created any apps yet."

Click the **Create app** button in the top right.

---

## Step 4: Fill in the Create App Form

Complete the form with the following values:

| Field | Value |
|-------|-------|
| **App name** | `Refrakt` |
| **App description** | `Analyzes Spotify playlists and generates instrumental music prompts for Suno AI` |
| **Website** | *(left blank)* |
| **Redirect URIs** | `http://127.0.0.1:8888/callback` |
| **API/SDKs** | Web API |

> **Note on Redirect URI:** Use `http://127.0.0.1:8888/callback` — not `localhost`. Spotify's dashboard blocks `http://localhost` and its auth server rejects `https://localhost`. The IP form `127.0.0.1` is accepted by both. A temporary local server listens on port 8888 to capture the OAuth callback token.

### Adding the Redirect URI

Type the URI and click **Add** to commit it as a tag before saving. It must use `https://` — Spotify will warn on `http://` and prevent adding it.

After clicking Add, the URI appears as a removable tag above the input:

---

## Step 5: Save the App

Click **Save**. Spotify creates the app and redirects to the **Basic Information** page.

---

## Step 6: Retrieve Credentials

On the Basic Information page you will find:

- **Client ID** — visible immediately
- **Client Secret** — click **View client secret** to reveal it

> **Security:** Treat the Client Secret like a password. Do not commit it to version control. Store it in a `.env` file (which should be in `.gitignore`).

### Your Credentials

| Key | Value |
|-----|-------|
| **Client ID** | *(from your Spotify Developer Dashboard)* |
| **Client Secret** | *(click "View client secret" to reveal)* |
| **Redirect URI** | `http://127.0.0.1:8888/callback` |
| **App Status** | Development mode |

---

## Step 7: Store Credentials Locally

Create a `.env` file in the project root:

```
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

---

## Scopes Required

For this project the following OAuth scopes are needed:

| Scope | Purpose |
|-------|---------|
| `playlist-read-private` | Read the "Wordless Work" playlist |
| `playlist-read-collaborative` | Access collaborative playlists if needed |
| `user-library-read` | Access saved tracks |

These are requested at OAuth authorization time — no extra dashboard config needed.

---

## Auth Flow

This project uses the **Authorization Code flow** (suitable for scripts with a local callback server):

1. Script opens a browser to Spotify's auth URL with your Client ID and scopes
2. User logs in and approves
3. Spotify redirects to `https://localhost:8888/callback?code=...`
4. Local server captures the `code`, exchanges it for an access token
5. Token is stored locally for subsequent API calls

Access tokens expire after 1 hour; use the refresh token to renew automatically.
