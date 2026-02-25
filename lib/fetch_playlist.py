#!/usr/bin/env python3
"""
fetch_playlist.py

Fetches all tracks from a Spotify playlist along with their audio features,
and writes the results to a JSON file for use in Suno prompt generation.

Usage:
    .venv/bin/python fetch_playlist.py

On first run: a browser will open for Spotify login. If it redirects to an
https://localhost page with an SSL error, copy the full URL from the address
bar and paste it back into the terminal when prompted.
"""

import json
import os
import sys
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

from pathlib import Path as _Path
load_dotenv(_Path(__file__).parent.parent / ".env")

PLAYLIST_NAME = "Wordless Work"
_BASE_DIR = _Path(__file__).parent.parent
OUTPUT_FILE = str(_BASE_DIR / "playlist_data.json")

SCOPES = "playlist-read-private playlist-read-collaborative"


def get_spotify_client():
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=os.environ["SPOTIFY_CLIENT_ID"],
        client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
        redirect_uri=os.environ["SPOTIFY_REDIRECT_URI"],
        scope=SCOPES,
        open_browser=True,
    ))


def find_playlist(sp, name):
    """Search user's playlists for one matching name."""
    offset = 0
    while True:
        result = sp.current_user_playlists(limit=50, offset=offset)
        for playlist in result["items"]:
            if playlist["name"].lower() == name.lower():
                return playlist
        if result["next"] is None:
            break
        offset += 50
    return None


def get_all_tracks(sp, playlist_id):
    """Fetch all tracks from a playlist, handling pagination.

    Uses /items endpoint (newer) since /tracks was deprecated by Spotify.
    The items endpoint returns track data under the 'item' key.
    """
    tracks = []
    offset = 0
    while True:
        result = sp._get(f"playlists/{playlist_id}/items", limit=100, offset=offset)
        for item in result["items"]:
            track = item.get("item")  # newer /items endpoint uses "item" not "track"
            if track and track.get("id") and track.get("type") == "track":
                tracks.append(track)
        if result["next"] is None:
            break
        offset += len(result["items"])
    return tracks


def build_track_record(track):
    artists = track["artists"]
    return {
        "id": track["id"],
        "name": track["name"],
        "artists": [a["name"] for a in artists],
        "album": track["album"]["name"],
        "release_year": (track["album"].get("release_date") or "")[:4],
        "duration_ms": track["duration_ms"],
        "popularity": track.get("popularity"),
        "explicit": track.get("explicit"),
    }


def main():
    print(f"Connecting to Spotify...")
    sp = get_spotify_client()

    user = sp.current_user()
    print(f"Logged in as: {user['display_name']}")

    print(f"Looking for playlist: '{PLAYLIST_NAME}'...")
    playlist = find_playlist(sp, PLAYLIST_NAME)
    if not playlist:
        print(f"ERROR: Could not find playlist '{PLAYLIST_NAME}'")
        print("Your playlists:")
        result = sp.current_user_playlists(limit=20)
        for p in result["items"]:
            print(f"  - {p['name']}")
        sys.exit(1)

    print(f"Found: '{playlist['name']}' ({playlist['id']})")
    print(f"Fetching tracks...")
    tracks = get_all_tracks(sp, playlist["id"])
    print(f"  {len(tracks)} tracks found")

    print(f"Building records...")
    records = [build_track_record(t) for t in tracks]

    output = {
        "playlist": {
            "id": playlist["id"],
            "name": playlist["name"],
            "total_tracks": len(records),
        },
        "tracks": records,
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nDone. Written to {OUTPUT_FILE}")
    print(f"Sample track:")
    print(json.dumps(records[0], indent=2))


if __name__ == "__main__":
    main()
