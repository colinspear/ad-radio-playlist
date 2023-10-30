# Aquarium Drunkard Radio

A dockerized Python FastAPI app that recreates the [Aquarium Drunkard Radio Show](https://aquariumdrunkard.com/category/sirius/) as a Spotify playlist. Updates weekly.

If you don't know [Aquarium Drunkard](https://aquariumdrunkard.com/), definitely go check them out and [support them on Patreon](https://www.patreon.com/aquariumdrunkard). 

## Requirements:

- Docker
- Python 3.11

## Registration

- Set up a Spotify Developers account and register a redirect URI to obtain a Client ID and Secret.

## Setup:

- Clone the repository and step inside.

```
$ git clone https://github.com/colinspear/ad-radio-playlist.git
$ cd ad-radio-playlist
```

- Set the required environment variables:

```
$ cp env-template .env
$ vi .env    # Replace `<VALUES>`'s with your values in vim or another editor.
```

## Usage
### Docker

1. Build the docker image:

```
$ docker build -t ad-radio-playlist .
```

2. Run the image, specifying your `.env` file and exposing port 8099:

```
$ docker run --env-file .env -p 8099:8099 ad-radio-playlist
```

3. Navigate to `127.0.0.1:8099`, click on "Authorize" and grant permissions when prompted.

### From source

1. Create a virtual environment (not required but highly recommended).
2. Install required packages with pip, set env vars, and run app.

```
$ pip install -r requirements.txt
$ set -a; source .env; set +a
$ uvicorn ad_radio_playlist:app --host 127.0.0.1 --port 8099
```

3. Navigate to `127.0.0.1:8099` (or `localhost:8099`) in a browser
4. Click on "Authorize" and grant permissions when prompted.

