# ad-radio-playlist

A Python script and automated workflow that recreates and updates the Aquarium Drunkard Radio Show playlist on Spotify each week.

## Features

- Scrape weekly track lists from Aquarium Drunkard via website or Gmail API
- Search for tracks on Spotify and collect URIs
- Create or update a Spotify playlist with the collected tracks
- Automatic token refresh locally; CI fails loudly on expired tokens to trigger secret rotation
- Scheduled via GitHub Actions to run weekly (early Tuesday morning US Eastern Time)
- Includes unit tests for core functionality

## Requirements

- Python 3.11 (or compatible 3.x)
- pip
- Spotify Developer account for CLIENT_ID, CLIENT_SECRET, and REDIRECT_URI
- (Optional) Google Cloud OAuth credentials for Gmail API scraping

## Installation

1. Clone the repo:
   ```bash
   git clone https://github.com/colinspear/ad-radio-playlist.git
   cd ad-radio-playlist
   ```

2. Install dependencies:
   ```bash
   python -m pip install --upgrade pip
   pip install -r requirements.txt google-api-python-client google-auth-oauthlib
   ```

3. Create an `.env` file:
   ```bash
   cp env-template .env
   ```
   Then edit `.env` to set:
   ```
   CLIENT_ID=<YOUR_SPOTIFY_CLIENT_ID>
   CLIENT_SECRET=<YOUR_SPOTIFY_CLIENT_SECRET>
   REDIRECT_URI=<YOUR_REDIRECT_URI>
   PLAYLIST_ID=<OPTIONAL_EXISTING_PLAYLIST_ID>
   ```
   Next, add your initial OAuth tokens (after completing the Spotify auth flow once):
   ```
   ACCESS_TOKEN=<YOUR_SPOTIFY_ACCESS_TOKEN>
   REFRESH_TOKEN=<YOUR_SPOTIFY_REFRESH_TOKEN>
   ```
   If you want to scrape via Gmail instead of web scraping, also add:
   ```
   GMAIL_CLIENT_ID=<YOUR_GOOGLE_OAUTH_CLIENT_ID>
   GMAIL_CLIENT_SECRET=<YOUR_GOOGLE_OAUTH_CLIENT_SECRET>
   GMAIL_ACCESS_TOKEN=<YOUR_GMAIL_ACCESS_TOKEN>
   GMAIL_REFRESH_TOKEN=<YOUR_GMAIL_REFRESH_TOKEN>
   ```

## Usage

Run the update script locally:
```bash
python ad_radio_playlist.py
```
The script will fetch the latest show, search Spotify for each track, and update (or create) your playlist.

## Automated Updates via GitHub Actions

A scheduled workflow is provided in `.github/workflows/weekly_ad_radio_playlist.yml`. It runs every Tuesday at 10:00 UTC (approximately 5 AM EST/6 AM EDT) and requires the following repository **secrets**:

```
CLIENT_ID
CLIENT_SECRET
REDIRECT_URI
ACCESS_TOKEN
REFRESH_TOKEN
PLAYLIST_ID
GMAIL_CLIENT_ID
GMAIL_CLIENT_SECRET
GMAIL_ACCESS_TOKEN
GMAIL_REFRESH_TOKEN
```

When the Spotify access token expires, the action will fail with a clear error, alerting you to rotate your tokens.

## Testing

Run unit tests with:
```bash
pytest
```

## License

[MIT License](LICENSE.md)

---

If you enjoy what Aquarium Drunkard does, get a subscription at https://aquariumdrunkard.com/ and consider supporting them on Patreon: https://www.patreon.com/aquariumdrunkard

