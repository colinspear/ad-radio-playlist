import base64
import json
from datetime import datetime
from pathlib import Path

import requests
import boto3

# Load env vars from .env
# should include CLIENT_ID, CLIENT_SECRET, ACCESS_TOKEN, and REFRESH_TOKEN

# tokens to 
def is_token_expired(access_token):
    """Check if the current access token is expired."""
    test_url = "https://api.spotify.com/v1/me/player/ad-radio-playlist"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    response = requests.get(test_url, headers=headers)
    return response.status_code == 401  # 401 status code indicates an expired or invalid token


def refresh_access_token(refresh_token, client_id, client_secret):
    """Refresh the access token using the refresh token."""
    token_url = 'https://accounts.spotify.com/api/token'
    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    }
    headers = {
        'Authorization': f'Basic {base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()}'
    }

    response = requests.post(token_url, data=payload, headers=headers)

    if response.status_code == 200:
        new_token_info = response.json()
        return new_token_info
    else:
        # TODO: Handle error (e.g., log it, raise an exception)
        return None


def __main__(event, context):
    time = _get_time()
    secrets = get_secret(secret_name, region)

    client_id = secrets["CLIENT_ID"]
    client_secret = secrets["CLIENT_SECRET"]
    access_token = secrets["ACCESS_TOKEN"]
    refresh_token = secrets["REFRESH_TOKEN"]

    if is_token_expired(access_token):
        print("Token expired, refreshing...")
        new_token_info = refresh_access_token(refresh_token, client_id, client_secret)

        if not new_token_info:
            raise Exception("Failed to refresh token")
        
        key_values = {
            'CLIENT_ID': client_id,
            'CLIENT_SECRET': client_secret,
            'ACCESS_TOKEN': new_token_info['access_token'],
            'REFRESH_TOKEN': refresh_token
        }
        update_secret(secret_name, key_values)
        
        access_token = new_token_info['access_token']
