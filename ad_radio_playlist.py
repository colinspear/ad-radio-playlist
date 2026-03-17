#!/usr/bin/env python3
"""
Aquarium Drunkard Radio → Spotify Playlist

Fetches the weekly AD show setlist from xmplaylist.com (SiriusXMU Ch. 35)
and updates a Spotify playlist with the tracks.

The show airs Wednesdays at 7–9 PM PT (10 PM – 12 AM ET).
Run this Thursday morning to catch the previous night's show.
"""

import argparse
import os
import sys
import base64
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv, find_dotenv, set_key

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

ON_CI = os.getenv("GITHUB_ACTIONS") == "true"

# Spotify creds are read lazily so --dry-run works without them
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
PLAYLIST_ID = os.getenv("PLAYLIST_ID")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")


def _require_spotify_env():
    """Validate that Spotify credentials are set. Called before any Spotify API use."""
    required = ["CLIENT_ID", "CLIENT_SECRET", "REFRESH_TOKEN"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        raise SystemExit(f"Error: Missing environment variables: {', '.join(missing)}")

PLAYLIST_NAME = "Aquarium Drunkard Radio"
PLAYLIST_DESCRIPTION = (
    "Songs from the Aquarium Drunkard Radio Show on SiriusXMU. "
    "Updated weekly. Setlist data via xmplaylist.com. "
    "Report issues: https://github.com/colinspear/ad-radio-playlist/issues"
)
BASE_URL = "https://api.spotify.com/v1"
XMPLAYLIST_STATION_URL = "https://xmplaylist.com/api/station/siriusxmu"
XMPLAYLIST_USER_AGENT = "ad-radio-playlist/2.0 (https://github.com/colinspear/ad-radio-playlist)"

# Show airs Wednesdays 7–9 PM America/Los_Angeles (handles PST/PDT automatically)
SHOW_TIMEZONE = "America/Los_Angeles"
SHOW_DAY_OF_WEEK = 2   # Wednesday (0=Mon ... 6=Sun)
SHOW_START_HOUR = 19    # 7 PM local
SHOW_END_HOUR = 21      # 9 PM local


# ---------------------------------------------------------------------------
# Spotify auth
# ---------------------------------------------------------------------------

def get_access_token():
    """Obtain a fresh Spotify access token using the refresh token."""
    refresh_token = os.getenv("REFRESH_TOKEN")
    if not refresh_token:
        raise EnvironmentError("REFRESH_TOKEN must be set as an environment variable.")
    auth_header = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    try:
        resp = requests.post(
            "https://accounts.spotify.com/api/token",
            data=payload, headers=headers, timeout=10,
        )
        resp.raise_for_status()
        access = resp.json().get("access_token")
        if not access:
            raise RuntimeError("No access token returned from Spotify")
        return access
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to refresh access token: {e}") from e


def get_auth_headers():
    """Return headers with a valid access token for Spotify API calls."""
    token = get_access_token()
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Spotify helpers
# ---------------------------------------------------------------------------

def get_user_id(headers):
    """Retrieve the Spotify user ID for the current credentials."""
    try:
        resp = requests.get(f"{BASE_URL}/me", headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json().get("id")
    except requests.RequestException as e:
        raise RuntimeError("Failed to fetch Spotify user ID") from e


def search_track(query, headers):
    """Search Spotify for a track and return its URI."""
    try:
        resp = requests.get(
            f"{BASE_URL}/search", headers=headers,
            params={"q": query, "type": "track", "limit": 1}, timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("tracks", {}).get("items", [])
        if not items:
            raise ValueError(f"No track found for query '{query}'")
        return items[0].get("uri")
    except requests.RequestException as e:
        raise RuntimeError(f"Search request failed for '{query}'") from e


def create_new_playlist(user_id, headers):
    """Create a new playlist and return its ID."""
    data = {
        "name": PLAYLIST_NAME,
        "description": PLAYLIST_DESCRIPTION,
        "public": True,
    }
    try:
        resp = requests.post(
            f"{BASE_URL}/users/{user_id}/playlists",
            headers=headers, json=data, timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("id")
    except requests.RequestException as e:
        raise RuntimeError("Failed to create new playlist") from e


def replace_playlist(playlist_id, uris, headers):
    """Replace all tracks in the playlist with the given URIs."""
    try:
        resp = requests.put(
            f"{BASE_URL}/playlists/{playlist_id}/tracks",
            headers=headers, json={"uris": uris}, timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError("Failed to replace playlist tracks") from e


# ---------------------------------------------------------------------------
# xmplaylist: fetch the AD show setlist
# ---------------------------------------------------------------------------

def get_show_window(reference_time=None):
    """
    Calculate the most recent AD show window (start, end) as UTC datetimes.

    The show airs Wednesdays at 7–9 PM America/Los_Angeles. This function
    handles PST/PDT transitions automatically via zoneinfo.

    Returns (start_utc, end_utc) for the most recent show that has already ended.
    """
    la = ZoneInfo(SHOW_TIMEZONE)
    now = reference_time or datetime.now(timezone.utc)
    now_la = now.astimezone(la)

    # Start from today in LA time and walk back to the most recent Wednesday
    candidate_date = now_la.date()
    days_since_wed = (candidate_date.weekday() - SHOW_DAY_OF_WEEK) % 7
    candidate_date -= timedelta(days=days_since_wed)

    # Build the show window in LA time
    show_start_la = datetime(
        candidate_date.year, candidate_date.month, candidate_date.day,
        SHOW_START_HOUR, 0, 0, tzinfo=la,
    )
    show_end_la = datetime(
        candidate_date.year, candidate_date.month, candidate_date.day,
        SHOW_END_HOUR, 0, 0, tzinfo=la,
    )

    # If the show hasn't ended yet, go back one week
    if show_end_la.astimezone(timezone.utc) > now:
        show_start_la -= timedelta(weeks=1)
        show_end_la -= timedelta(weeks=1)

    return show_start_la.astimezone(timezone.utc), show_end_la.astimezone(timezone.utc)


def fetch_xmplaylist_tracks(start_dt, end_dt, max_pages=20):
    """
    Fetch tracks played on SiriusXMU between start_dt and end_dt (UTC).

    Paginates backward through the xmplaylist API, collecting tracks whose
    timestamps fall within the window.

    Returns a list of dicts with keys: title, artists, spotify_id, timestamp.
    Ordered chronologically (earliest first).
    """
    headers = {"User-Agent": XMPLAYLIST_USER_AGENT}
    collected = []
    last_cursor = None

    for page in range(max_pages):
        params = {}
        if last_cursor:
            params["last"] = last_cursor

        try:
            resp = requests.get(
                XMPLAYLIST_STATION_URL,
                headers=headers, params=params, timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise RuntimeError(f"xmplaylist API request failed (page {page}): {e}") from e

        results = data.get("results", [])
        if not results:
            break

        went_past_window = False
        for entry in results:
            ts_str = entry.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue

            if ts < start_dt:
                went_past_window = True
                break

            if start_dt <= ts <= end_dt:
                track = entry.get("track", {})
                spotify = entry.get("spotify") or {}
                collected.append({
                    "title": track.get("title", ""),
                    "artists": track.get("artists", []),
                    "spotify_id": spotify.get("id"),
                    "timestamp": ts,
                })

        if went_past_window:
            break

        # Use the last entry's id as the pagination cursor
        last_cursor = results[-1].get("id")
        if not data.get("next"):
            break

    # Return in chronological order (API returns newest first)
    collected.sort(key=lambda t: t["timestamp"])
    return collected


def tracks_to_spotify_uris(tracks, spotify_headers):
    """
    Convert xmplaylist track dicts to Spotify URIs.

    Uses the Spotify ID directly when available; falls back to a text search.
    Returns (uris, skipped) where skipped is a list of tracks that couldn't
    be matched.
    """
    uris = []
    skipped = []

    for t in tracks:
        artists_str = (
            ", ".join(t["artists"]) if isinstance(t["artists"], list) else t["artists"]
        )

        # Prefer direct Spotify ID from xmplaylist
        if t.get("spotify_id"):
            uri = f"spotify:track:{t['spotify_id']}"
            uris.append(uri)
            print(f"  ✓ {artists_str} – {t['title']} (direct ID)")
            continue

        # Fallback: search by artist + title
        query = f"{artists_str} {t['title']}"
        try:
            uri = search_track(query, spotify_headers)
            uris.append(uri)
            print(f"  ~ {artists_str} – {t['title']} (search match)")
        except (ValueError, RuntimeError) as e:
            print(f"  ✗ {artists_str} – {t['title']} — skipped: {e}")
            skipped.append(t)

    return uris, skipped


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def update_playlist(dry_run=False):
    """Main flow: fetch setlist from xmplaylist, resolve Spotify URIs, update playlist.

    If dry_run is True, fetches and prints the setlist but does not touch Spotify.
    No Spotify credentials are needed for dry-run mode.
    """
    # 1. Determine the show window
    start, end = get_show_window()
    print(f"Show window: {start.isoformat()} → {end.isoformat()}")

    # 2. Fetch tracks from xmplaylist
    tracks = fetch_xmplaylist_tracks(start, end)
    if not tracks:
        raise RuntimeError(
            "No tracks found for the show window. The show may not have aired, "
            "or xmplaylist data may have expired. Try running sooner after the show."
        )
    print(f"Found {len(tracks)} tracks from xmplaylist\n")

    for i, t in enumerate(tracks, 1):
        artists_str = (
            ", ".join(t["artists"]) if isinstance(t["artists"], list) else t["artists"]
        )
        spotify_tag = " [spotify]" if t.get("spotify_id") else " [no spotify id]"
        print(f"  {i:2d}. {artists_str} – {t['title']}{spotify_tag}")

    if dry_run:
        has_spotify = sum(1 for t in tracks if t.get("spotify_id"))
        print(f"\n[dry-run] {has_spotify}/{len(tracks)} tracks have direct Spotify IDs.")
        print("[dry-run] Skipping Spotify playlist update.")
        return None, len(tracks)

    # 3. Resolve Spotify URIs (requires creds)
    _require_spotify_env()
    spotify_headers = get_auth_headers()
    uris, skipped = tracks_to_spotify_uris(tracks, spotify_headers)

    if not uris:
        raise RuntimeError("No Spotify URIs resolved — nothing to add to the playlist.")

    print(f"\n{len(uris)} matched, {len(skipped)} skipped")

    # 4. Update (or create) the playlist
    user_id = get_user_id(spotify_headers)
    pid = PLAYLIST_ID
    if not pid:
        print("Creating new playlist...")
        pid = create_new_playlist(user_id, spotify_headers)
        if dotenv_path:
            set_key(dotenv_path, "PLAYLIST_ID", pid)
        print(f"Saved new PLAYLIST_ID: {pid}")

    print(f"Updating playlist {pid} with {len(uris)} tracks...")
    replace_playlist(pid, uris, spotify_headers)
    print("Playlist update complete.")
    return pid, len(uris)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch the AD Radio show setlist and update a Spotify playlist."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and display the setlist from xmplaylist without touching Spotify. "
             "No Spotify credentials required.",
    )
    args = parser.parse_args()

    try:
        update_playlist(dry_run=args.dry_run)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
