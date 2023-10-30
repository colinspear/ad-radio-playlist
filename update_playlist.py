#!/home/cspear/.venv/ad-radio-playlist/bin/python

import os
import re
import requests
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from bs4 import BeautifulSoup


# Spotify credentials
client_id = os.getenv("SPOTIPY_CLIENT_ID")
client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
redirect_uri = os.getenv("REDIRECT_URI")
playlist_id = os.getenv("PLAYLIST_ID")
print(playlist_id)

auth_url = 'https://accounts.spotify.com/authorize'
scope = [
    "playlist-modify-public", 
    # "ugc-image-upload", 
    "playlist-read-private",
    "playlist-modify-private"
]

playlist_name = "Aquarium Drunkard Radio"
playlist_description = "Songs from the Aquarium Drunkard Radio Show. Updated weekly on Thursdays. Not always accurate if the song is not on Spotify. Report any issues here: https://github.com/colinspear/ad-radio-playlist/issues"

app = FastAPI()

def get_playlist_id(playlist_id=playlist_id):
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
    print(response.json())
    if response.status_code == 200:
        access_token = response.json()["access_token"]
        return {"Authorization": "Bearer " + access_token}
    else:
        return {"Authorization failed: ": response.json()}


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
    
    if response.status_code == 200:
        show_content = response.content
    else: 
        print(f'Request to {url} returned status code {response.status_code}')
    
    soup = BeautifulSoup(show_content, 'html.parser')
    # image = soup.find("figure").find("a").get("href")
    
    main_text = soup.find("div", {"class": "entry-content"}).get_text()
    songs_text = [s for s in main_text.split('\n') if re.match(r'SIRIUS', s)][0]

    songs_list = songs_text.split(' ++ ')[1:]
    return songs_list


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
    print(auth_url)
    return HTMLResponse(content=f'<a href="{auth_url}">Authorize</a>')


@app.get("/callback")
async def callback(code):
    headers = get_access_token(code)
    # print(f"Headers: {headers}")
    # print(f'Scope: ', scope)
    playlist_id = get_playlist_id()
    print('florf', playlist_id)

    response = requests.get("https://api.spotify.com/v1/me", headers=headers)
    user_id = response.json()["id"]
    print(f"User ID: {user_id}")

    latest_episode = get_latest_episode()
    print("Latest AD Radio episode: ", latest_episode)
   
    artists_songs = get_artists_songs(latest_episode)
    # print(artists_songs)
    track_uris = create_track_uri_list(artists_songs, headers)
    
    if not playlist_id:
        print('No saved playlist ID found. Creating new playlist now...')
        playlist_id = create_new_playlist(user_id, headers, playlist_name=playlist_name, playlist_description=playlist_description)
        populate_playlist(playlist_id, headers, track_uris)
        print(f'Created new playlist with ID {playlist_id}. Please include in .env file if you wish to update this playlist in the future.')
    else: 
        populate_playlist(playlist_id, headers, track_uris)




# try:
#     # Load the refresh token from the file
#     with open('refresh_token.txt') as rf:
#         refresh_token = rf.readline()

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
