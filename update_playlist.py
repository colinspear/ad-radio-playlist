#!/home/cspear/.venv/ad-radio-playlist/bin/python

import os
import re
import sys
from zoneinfo import ZoneInfo
import requests
from pathlib import Path
from datetime import datetime, timedelta

import spotipy
from bs4 import BeautifulSoup
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv



def date_range(start_date, end_date):
    for n in range(int ((end_date - start_date).days)+1):
        yield start_date + timedelta(n)


def scan_last_week(date_list, issue_number):
    issue_range = list(range(60, issue_number+2))
    issue_range.reverse()
    for date in date_list:
        d = date[0]
        tz = date[1].lower()
        for i in issue_range:
            url = f"https://aquariumdrunkard.com/{d.year}/{d.month:02}/{d.day:02}/the-aquarium-drunkard-show-sirius-xmu-7pm-{tz}-channel-35-{i}/"
            #url = "https://aquariumdrunkard.com/2023/03/22/the-aquarium-drunkard-show-sirius-xmu-7pm-pdt-channel-35-82/"
            response = requests.get(url)
            if response.status_code == 200:
                return url
    return None


def get_playlist_id(playlist_name):
    playlists = sp.current_user_playlists()
    for playlist in playlists["items"]:
        if playlist["name"] == playlist_name:
            return playlist["id"]
    return None


def create_playlist(sp, artists_songs):
    # 1. Get the Spotify user ID
    current_user = sp.current_user()
    user_id = current_user["id"]
    
    # 2. Create a new playlist
    playlist_name = "Aquarium Drunkard Radio"
    playlist_id = get_playlist_id(playlist_name)
    if playlist_id is None:
        playlist = sp.user_playlist_create(user_id, playlist_name)
        playlist_id = playlist["id"]
    
    # 3. Search for each song and add it to the playlist
    tracks = []
    for artist, song in artists_songs.items():
        result = sp.search(q=f"{artist} {song}", type="track")
        if len(result["tracks"]["items"]) > 0:
            tracks.append(result["tracks"]["items"][0]["id"])
    
    # 4. Add all songs to the playlist
    sp.playlist_replace_items(playlist_id, tracks)

    # 5. Return the playlist information
    return sp.playlist(playlist_id)

c_path = Path("/home/cspear/external/ad-radio-playlist")
env_path = c_path / ".env"
load_dotenv(dotenv_path=str(c_path/".env"))

client_id = os.getenv("SPOTIPY_CLIENT_ID")
client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")

# Spotify credentials
redirect_uri='http://localhost:8099/'
scope = "playlist-modify-public,ugc-image-upload"

with open(c_path / "urls.txt", "r") as f:
    last_url = f.readlines()[-1]

last_issue = int(last_url.split("-")[-1].replace("/", ""))
t = datetime.now()
today = datetime(t.year, t.month, t.day, t.hour, t.minute, tzinfo=ZoneInfo("America/Los_Angeles"))
start_date = (today - timedelta(days=7))

#date_list = list(date_range(start_date, today))
date_list = [(d, d.tzname()) for d in date_range(start_date, today)]
date_list.reverse()

url = scan_last_week(date_list, last_issue)

if not url:
    print("No playlist found for the week of " + str(start_date))
    sys.exit()

response = requests.get(url)

if response.status_code == 200:
    html_content = response.content
    soup = BeautifulSoup(html_content, 'html.parser')
    image = soup.find("figure").find("a").get("href")
    main_text = soup.find("div", {"class": "entry-content"}).get_text()
    songs_text = [s for s in main_text.split('\n') if re.match(r'SIRIUS', s)][0]

    artists_songs = {}
    songs_list = songs_text.split(' ++ ')[1:]
    for s in songs_list:
        try:
            artists_songs[s.split(' – ')[0]] = s.split(' – ')[1]
        except IndexError:
            artists_songs[s.split(' :: ')[0]] = s.split(' :: ')[1]
        # Do something with the HTML content, like save it to a file or parse it
else:
    print(f"Failed to fetch the URL {url}. Response code: {response.status_code}")
    sys.exit()

sp_oauth = SpotifyOAuth(
    client_id=client_id, client_secret=client_secret, 
    redirect_uri=redirect_uri, scope=scope)


try:
    # Load the refresh token from the file
    with open(c_path / "refresh_token.txt", "r") as f:
        refresh_token = f.read()
    access_token = sp_oauth.refresh_access_token(refresh_token)["access_token"]

except FileNotFoundError:
    authorization_url = sp_oauth.get_authorize_url()
    print(f"Please go to the following URL and grant the necessary permissions: {authorization_url}")

    # Extract the authorization code from the URL
    authorization_code = input("Enter the authorization code from the URL: ")

    # Request an access token
    token_info = sp_oauth.get_access_token(authorization_code)
    access_token = token_info["access_token"]
    refresh_token = token_info["refresh_token"]

    # Save the refresh token to a file
    with open(c_path / "refresh_token.txt", "w") as f:
        f.write(refresh_token)
        
sp = spotipy.Spotify(auth=access_token)

playlist = create_playlist(sp, artists_songs)

# Upload the new image to Spotify and get its URL
#image_url = sp.playlist_upload_cover_image(playlist['id'], image)

# Update the playlist with the new image URL
#sp.playlist_cover_image(playlist_id, [image_url])
    

with open(c_path / "urls.txt", "a") as f:
    f.write(url + "\n")

print(f"{today}: Created playlist {playlist['name']} with {playlist['tracks']['total']} songs from {url}.")
