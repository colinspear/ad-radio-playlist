#!/usr/bin/env python3

import os
import re
import requests
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from bs4 import BeautifulSoup


# Validate required environment variables
import sys
required_env = ["CLIENT_ID", "CLIENT_SECRET", "REDIRECT_URI"]
missing_env = [var for var in required_env if not os.getenv(var)]
if missing_env:
    raise SystemExit(f"Error: Missing environment variables: {', '.join(missing_env)}")

# Spotify credentials
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
redirect_uri = os.getenv("REDIRECT_URI")
playlist_id = os.getenv("PLAYLIST_ID")

auth_url = 'https://accounts.spotify.com/authorize'
scope = [
    "playlist-modify-public", 
    # "ugc-image-upload", 
    # "playlist-read-private",
    "playlist-modify-private"
]

playlist_name = "Aquarium Drunkard Radio"
playlist_description = "Songs from the Aquarium Drunkard Radio Show. Updated weekly on Thursdays. Not always accurate if the song is not on Spotify. Report any issues here: https://github.com/colinspear/ad-radio-playlist/issues"

app = FastAPI()

def get_playlist_id(playlist_id_arg=None):
    if playlist_id_arg is not None:
        return playlist_id_arg
    return playlist_id


def get_access_token(auth_code: str):
    response = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": redirect_uri,
        },
        auth=(client_id, client_secret),
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        raise RuntimeError(f"Failed to get access token ({response.status_code}): {response.text}") from e
    data = response.json()
    access_token = data.get("access_token")
    if not access_token:
        raise RuntimeError("Failed to get access token: 'access_token' not found in response")
    return {"Authorization": f"Bearer {access_token}"}


def get_latest_episode():
    sirius_url = 'https://aquariumdrunkard.com/category/sirius'
    response = requests.get(sirius_url)
    if response.status_code == 200:
        sirius_content = response.content
    else: 
        print(f'Request to {sirius_url} returned status code {response.status_code}')
    soup = BeautifulSoup(sirius_content, 'html.parser')
    episodes = soup.find_all("h2", {"class": "entry-title"})
    latest_episode = episodes[0].find('a')['href']
    # image_text = episodes[0].find('a')['style']
    # image_url = image_text[image_text.find("(")+1:image_text.find(")")]
    
    return latest_episode


def get_artists_songs(url):
    response = requests.get(url)
    if response.status_code != 200:
        raise RuntimeError(f"Failed to fetch show page ({response.status_code}): {url}")
    # Search raw HTML for the tracklist line starting with 'SIRIUS ++'
    if hasattr(response, 'content') and isinstance(response.content, (bytes, bytearray)):
        html = response.content.decode('utf-8', errors='ignore')
    else:
        html = getattr(response, 'text', '')
    match = re.search(r"SIRIUS \+\+ [^<]+", html)
    if not match:
        raise RuntimeError(f"No song list found on page: {url} (page may be paywalled or structure changed)")
    songs_text = match.group(0)
    parts = songs_text.split(' ++ ')
    if len(parts) < 2:
        raise RuntimeError(f"Unexpected song list format on page: {url}")
    return parts[1:]


def get_track_uri(artist_song, headers):
    # Example usage:
    # search_query = "Junior Murvin Police and Thieves"
    # headers = {"Authorization": "Bearer YOUR_ACCESS_TOKEN_HERE"}  # Replace with your actual access token
    # result = search_track(search_query, headers)
    base_url = "https://api.spotify.com/v1/search"
    params = {
        'q': artist_song,
        'type': 'track',
        'limit': 1
    }
    response = requests.get(base_url, headers=headers, params=params)
    if response.status_code == 200:
        track_uri = response.json()['tracks']['items'][0]['uri']
        return track_uri
    else:
        return {"error": response.json()}

      
def create_track_uri_list(artists_songs, headers):
    track_uri_list = [get_track_uri(a_s, headers) for a_s in artists_songs]
    return track_uri_list  

  
def create_new_playlist(user_id, headers, playlist_name, playlist_description):
    
    params = {
        "name": playlist_name,
        "description": playlist_description,
        "public": True,
    }

    url = f"https://api.spotify.com/v1/users/{user_id}/playlists"
    response = requests.post(url=url, headers=headers, json=params)
    # print(f"HTTP Status Code: {response.status_code}")
    
    if response.status_code != 201:
        print(f"Error: {response.content}")
        response.raise_for_status()
    else:
        playlist_id = response.json()["id"]
        print(f"Playlist ID: {playlist_id}")

    return playlist_id


def populate_playlist(playlist_id, headers, track_uris):
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    response = requests.put(
        url=url,
        headers=headers,
        json={"uris": track_uris},
    )

    if response.status_code == 201 or response.status_code == 200:
        return {"message": "Tracks replaced successfully!"}
    else:
        return {"error": response.json()}

@app.get("/")
async def auth():
    auth_url = f"https://accounts.spotify.com/authorize?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scope={' '.join(scope)}"
    return HTMLResponse(content=f'<a href="{auth_url}">Authorize</a>')


from fastapi import HTTPException

@app.get("/callback")
async def callback(code):
    headers = get_access_token(code)
    playlist_id = get_playlist_id()
    response = requests.get("https://api.spotify.com/v1/me", headers=headers)
    user_id = response.json().get("id")
    if not user_id:
        raise HTTPException(status_code=502, detail="Failed to fetch user ID from Spotify")
    print(f"User ID: {user_id}")
    latest_episode = get_latest_episode()
    print("Latest AD Radio episode:", latest_episode)
    try:
        artists_songs = get_artists_songs(latest_episode)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=f"Failed to parse song list: {e}")
    track_uris = create_track_uri_list(artists_songs, headers)
    
    if not playlist_id:
        print('No saved playlist ID found. Creating new playlist now...')
        playlist_id = create_new_playlist(user_id, headers, playlist_name=playlist_name, playlist_description=playlist_description)
        populate_playlist(playlist_id, headers, track_uris)
        print(f'Created new playlist with ID {playlist_id}. Please include in .env file if you wish to update this playlist in the future.')
    else: 
        populate_playlist(playlist_id, headers, track_uris)




# if run as script, start the FastAPI server
if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8099"))
    uvicorn.run("ad_radio_playlist:app", host=host, port=port)

#     access_token = sp_oauth.refresh_access_token(refresh_token)["access_token"]

# except FileNotFoundError:
#     authorization_url = sp_oauth.get_authorize_url()
#     print(f"Please go to the following URL and grant the necessary permissions: {authorization_url}")

#     # Extract the authorization code from the URL
#     authorization_code = input("Enter the authorization code from the URL: ")

#     # Request an access token
#     token_info = sp_oauth.get_access_token(authorization_code)
#     access_token = token_info["access_token"]
#     refresh_token = token_info["refresh_token"]

#     # Save the refresh token to a file
#     with open("refresh_token.txt", "w") as f:
#         f.write(refresh_token)

# Upload the new image to Spotify and get its URL
#image_url = sp.playlist_upload_cover_image(playlist['id'], image_url)

# Update the playlist with the new image URL
#sp.playlist_cover_image(playlist_id, [image_url])
