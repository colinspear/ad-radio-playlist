#!/usr/bin/env python3

import os
import re
import requests
import base64
from pathlib import Path
from dotenv import load_dotenv, find_dotenv, set_key
from bs4 import BeautifulSoup

# Load environment variables from .env
dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

# Spotify credentials
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
PLAYLIST_ID = os.getenv("PLAYLIST_ID")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")

PLAYLIST_NAME = "Aquarium Drunkard Radio"
PLAYLIST_DESCRIPTION = (
    "Songs from the Aquarium Drunkard Radio Show. "
    "Updated weekly on Thursdays. Not always accurate if the song is not on Spotify. "
    "Report issues: https://github.com/colinspear/ad-radio-playlist/issues"
)
BASE_URL = "https://api.spotify.com/v1"

# Validation
if not CLIENT_ID or not CLIENT_SECRET:
    raise EnvironmentError("CLIENT_ID and CLIENT_SECRET must be set in .env")


def is_token_expired(token):
    """Return True if the access token is expired (HTTP 401)."""
    try:
        resp = requests.get(f"{BASE_URL}/me", headers={"Authorization": f"Bearer {token}"}, timeout=10)
        return resp.status_code == 401
    except requests.RequestException as e:
        raise RuntimeError("Failed to validate access token") from e


def refresh_tokens():
    """Use the refresh token to obtain a new access token and update .env."""
    if not REFRESH_TOKEN:
        raise EnvironmentError("REFRESH_TOKEN must be set in .env to refresh tokens.")
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN,
    }
    auth_header = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    try:
        resp = requests.post("https://accounts.spotify.com/api/token", data=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        new_access = data.get("access_token")
        new_refresh = data.get("refresh_token", REFRESH_TOKEN)
        set_key(dotenv_path, "ACCESS_TOKEN", new_access)
        set_key(dotenv_path, "REFRESH_TOKEN", new_refresh)
        return new_access
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to refresh token: {e}") from e


def get_auth_headers():
    """Get headers with a valid access token, refreshing if necessary."""
    if not ACCESS_TOKEN:
        raise EnvironmentError("ACCESS_TOKEN must be set in .env")
    token = ACCESS_TOKEN
    if is_token_expired(token):
        token = refresh_tokens()
    return {"Authorization": f"Bearer {token}"}


def get_user_id(headers):
    """Retrieve the Spotify user ID for the current credentials."""
    try:
        resp = requests.get(f"{BASE_URL}/me", headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json().get("id")
    except requests.RequestException as e:
        raise RuntimeError("Failed to fetch Spotify user ID") from e


def search_track(query, headers):
    """Search for a track and return its Spotify URI."""
    try:
        resp = requests.get(
            f"{BASE_URL}/search", headers=headers,
            params={"q": query, "type": "track", "limit": 1}, timeout=10
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
        resp = requests.post(f"{BASE_URL}/users/{user_id}/playlists", headers=headers, json=data, timeout=10)
        resp.raise_for_status()
        return resp.json().get("id")
    except requests.RequestException as e:
        raise RuntimeError("Failed to create new playlist") from e


def replace_playlist(playlist_id, uris, headers):
    """Replace all tracks in the playlist with the given URIs."""
    try:
        resp = requests.put(f"{BASE_URL}/playlists/{playlist_id}/tracks", headers=headers, json={"uris": uris}, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError("Failed to replace playlist tracks") from e


def get_latest_episode_url():
    """Scrape the Aquarium Drunkard site for the latest episode URL."""
    url = "https://aquariumdrunkard.com/category/sirius"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        link = soup.find("h2", {"class": "entry-title"}).find("a")
        return link.get("href")
    except Exception as e:
        raise RuntimeError("Failed to fetch latest episode URL") from e


def get_artists_songs(episode_url):
    """Parse the episode page and extract the list of 'Artist - Song' strings."""
    try:
        resp = requests.get(episode_url, timeout=10)
        resp.raise_for_status()
        text = BeautifulSoup(resp.content, "html.parser").find("div", {"class": "entry-content"}).get_text()
        line = next((l for l in text.splitlines() if l.startswith("SIRIUS")), None)
        if not line:
            raise ValueError("No song list found on episode page")
        return line.split(" ++ ")[1:]
    except Exception as e:
        raise RuntimeError("Failed to parse artists and songs") from e

# Email-based scraping using Gmail API
def get_gmail_service():
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as e:
        raise ImportError("Please install google-api-python-client and google-auth-oauthlib to use Gmail scraping") from e
    client_id = os.getenv("GMAIL_CLIENT_ID")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET")
    token = os.getenv("GMAIL_ACCESS_TOKEN")
    refresh_token = os.getenv("GMAIL_REFRESH_TOKEN")
    if not all([client_id, client_secret, token, refresh_token]):
        raise EnvironmentError(
            "Gmail API credentials must be set in .env: GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_ACCESS_TOKEN, GMAIL_REFRESH_TOKEN"
        )
    creds = Credentials(
        token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret
    )
    service = build("gmail", "v1", credentials=creds)
    return service

def get_playlist_entries_from_email():
    service = get_gmail_service()
    result = service.users().messages().list(
        userId="me",
        q="from:aquariumdrunkard@96110637.mailchimpapp.com",
        # q="from:colinspear@gmail.com",
        maxResults=1
    ).execute()
    messages = result.get("messages", [])
    print(messages)
    if not messages:
        raise RuntimeError("No email found from Aquarium Drunkard")
    msg_id = messages[0]["id"]
    msg = service.users().messages().get(
        userId="me", id=msg_id, format="full"
    ).execute()
    payload = msg.get("payload", {})
    html = None
    def _extract_html(part):
        data = part.get("body", {}).get("data")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8")
        return None
    if payload.get("mimeType") == "text/html":
        html = _extract_html(payload)
    elif "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/html":
                html = _extract_html(part)
                if html:
                    break
    if not html and "parts" in payload:
        def _find_html(parts):
            for p in parts:
                if p.get("mimeType") == "text/html":
                    return _extract_html(p)
                if "parts" in p:
                    sub = _find_html(p.get("parts"))
                    if sub:
                        return sub
            return None
        html = _find_html(payload.get("parts", []))
    if not html:
        raise RuntimeError("Could not find HTML content in email")
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = soup.find_all("p")
    line = None
    for p in paragraphs:
        text = p.get_text().strip()
        if re.match(r"^SIRIUS\s+\d+:", text):
            line = text
            break
    if not line:
        raise RuntimeError("No SIRIUS track list found in email")
    content = line.split(":", 1)[1].strip()
    parts = [item.strip() for item in content.split(" ++ ")]
    entries = [item for item in parts if "–" in item]
    return entries


def update_playlist():
    """Main flow: refresh token, scrape, search, and update Spotify playlist."""
    headers = get_auth_headers()
    user_id = get_user_id(headers)
    # Fetch playlist entries from the latest email
    entries = get_playlist_entries_from_email()
    print(f"Parsed {len(entries)} song entries from email")
    uris = []
    for entry in entries:
        try:
            uri = search_track(entry, headers)
            uris.append(uri)
            print(f"Matched '{entry}' -> {uri}")
        except Exception as e:
            print(f"Warning: {e}")
    pid = PLAYLIST_ID
    if not pid:
        print("Creating new playlist...")
        pid = create_new_playlist(user_id, headers)
        set_key(dotenv_path, "PLAYLIST_ID", pid)
        print(f"Saved new PLAYLIST_ID: {pid}")
    print(f"Updating playlist {pid} with {len(uris)} tracks...")
    replace_playlist(pid, uris, headers)
    print("Playlist update complete.")
    return pid, len(uris)


if __name__ == "__main__":
    try:
        update_playlist()
    except Exception as e:
        print(f"Error: {e}")
        exit(1)
