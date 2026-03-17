# ad-radio-playlist

A Python script that builds a Spotify playlist from the weekly [Aquarium Drunkard](https://aquariumdrunkard.com/) Radio Show on SiriusXMU (Ch. 35).

## Architecture

```
xmplaylist.com API  →  filter to show window  →  Spotify API  →  playlist updated
(SiriusXMU Ch. 35)     (Wed 7–9 PM Pacific)      (direct IDs     
                                                   + fallback search)
```

**Data source**: [xmplaylist.com](https://xmplaylist.com/) tracks every song played on SiriusXM stations in real time. The free `/api/station/siriusxmu` endpoint returns recently played tracks with timestamps, artist/title metadata, and (usually) Spotify track IDs. No API key is needed. [API docs](https://xmplaylist.com/docs).

**Previous approach**: This project originally scraped the setlist from the AD weekly Mailchimp newsletter via the Gmail API. That broke when AD stopped including the setlist in the email. The xmplaylist approach is simpler (no Gmail creds) and more reliable (Spotify IDs come from the API, so most tracks don't need a text search).

## How it works

1. **Calculate the show window**: The show airs Wednesdays 7–9 PM Pacific. The script uses `zoneinfo` to convert this to UTC, handling PST/PDT transitions automatically.
2. **Fetch tracks from xmplaylist**: Paginates backward through SiriusXMU's play history, collecting tracks whose timestamps fall within the 2-hour show window.
3. **Resolve Spotify URIs**: Uses the Spotify track ID from xmplaylist directly when available (most tracks). Falls back to a Spotify search by artist + title for the rest.
4. **Update the playlist**: Replaces the Spotify playlist contents with the matched tracks, in chronological show order.

## Requirements

- Python 3.11+ (uses `zoneinfo` from stdlib, available since 3.9)
- A [Spotify Developer app](https://developer.spotify.com/dashboard) for `CLIENT_ID`, `CLIENT_SECRET`, and a refresh token

## Setup

```bash
git clone https://github.com/colinspear/ad-radio-playlist.git
cd ad-radio-playlist
pip install -r requirements.txt
cp env-template .env
```

Edit `.env` with your Spotify credentials. You'll need to complete the [Spotify authorization code flow](https://developer.spotify.com/documentation/web-api/tutorials/code-flow) once to get a `REFRESH_TOKEN`. See `authorization.py` for helper functions.

## Usage

### Full run (updates Spotify playlist)

```bash
python ad_radio_playlist.py
```

Requires Spotify credentials in `.env`. Creates a new playlist if `PLAYLIST_ID` is blank.

### Dry run (test the xmplaylist fetch without Spotify)

```bash
python ad_radio_playlist.py --dry-run
```

Fetches the setlist from xmplaylist and prints it to stdout. **Does not require any Spotify credentials.** Use this to verify the xmplaylist API is returning data and the show window calculation is correct.

Example output:
```
Show window: 2025-03-20T02:00:00+00:00 → 2025-03-20T04:00:00+00:00
Found 28 tracks from xmplaylist

   1. Dungen – Peri Snansen [spotify]
   2. Broadcast – Corporeal [spotify]
   3. Mdou Moctar – Afrique Victime [spotify]
   ...

[dry-run] 26/28 tracks have direct Spotify IDs.
[dry-run] Skipping Spotify playlist update.
```

### Manual trigger via GitHub Actions

The workflow supports `workflow_dispatch`, so you can trigger it manually from the Actions tab in GitHub without waiting for the cron schedule.

## Automated scheduling

The GitHub Actions workflow (`.github/workflows/weekly_ad_radio_playlist.yml`) runs at **06:00 UTC every Thursday** (~1 AM Eastern, ~10 PM Pacific Wednesday — roughly 1 hour after the show ends).

Required repository secrets:
```
CLIENT_ID
CLIENT_SECRET
REFRESH_TOKEN
PLAYLIST_ID
```

## Key files

| File | Purpose |
|------|---------|
| `ad_radio_playlist.py` | Main script. All logic lives here. |
| `authorization.py` | Helper functions for the initial Spotify OAuth flow. |
| `tests/test_ad_radio_playlist.py` | Unit tests (pytest). Covers show window calculation, xmplaylist parsing, and Spotify URI resolution. |
| `.github/workflows/weekly_ad_radio_playlist.yml` | GitHub Actions cron workflow. |
| `env-template` | Template for `.env` file. |

## Configuration

Show timing constants are at the top of `ad_radio_playlist.py`:

```python
SHOW_TIMEZONE = "America/Los_Angeles"
SHOW_DAY_OF_WEEK = 2   # Wednesday (0=Mon ... 6=Sun)
SHOW_START_HOUR = 19    # 7 PM local
SHOW_END_HOUR = 21      # 9 PM local
```

If the show changes its time slot, update these values and adjust the cron schedule in the workflow file accordingly.

## Known limitations

- **xmplaylist data retention**: The free API endpoint returns "recently played" tracks. It's unclear exactly how far back this goes. Running within a few hours of the show ending is safest. The cron is set to 1 hour after.
- **Spotify matching**: ~90% of tracks get a direct Spotify ID from xmplaylist. The rest fall back to a text search, which can miss obscure tracks or match the wrong version.
- **xmplaylist tracks everything on SiriusXMU**, not just the AD show. The script filters by timestamp, but if SiriusXMU plays a song at 7:01 PM Pacific that isn't part of the AD show (e.g., during a handoff), it'll be included. In practice this is rarely an issue.

## Testing

```bash
pytest
```

Tests cover:
- Show window calculation across PST/PDT, different days of the week, mid-show edge case
- xmplaylist response parsing and timestamp filtering
- Spotify URI resolution (direct ID path and search fallback)

## Dependencies

Just two runtime dependencies (see `requirements.txt`):
- `requests` — HTTP client for xmplaylist and Spotify APIs
- `python-dotenv` — loads `.env` file

## License

[MIT License](LICENSE.md)

---

If you enjoy what Aquarium Drunkard does, get a subscription at https://aquariumdrunkard.com/ and consider supporting them on Patreon: https://www.patreon.com/aquariumdrunkard
