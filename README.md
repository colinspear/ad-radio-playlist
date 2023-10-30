# Aquarium Drunkard Radio

A dockerized Python FastAPI app that recreates the [Aquarium Drunkard Radio Show](https://aquariumdrunkard.com/category/sirius/) as a Spotify playlist. Updates weekly.

If you don't know [Aquarium Drunkard](https://aquariumdrunkard.com/), definitely go check them out and [support them on Patreon](https://www.patreon.com/aquariumdrunkard). 

# Requirements:

- Docker
- Python 3.11

# Registration

- Set up a Spotify Developers account and register a redirect URI to obtain a Client ID and Secret.

# Build instructions:

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

- Build the docker image:

```
$ docker build -t ad-radio-playlist .
```

- Run the image, specifying your `.env` file and exposing port 8099:

```
$ docker run --env-file .env -p 8099:8099 ad-radio-playlist
```

- Navigate to `127.0.0.1:8099`
- Click on "Authorize"
- Grant permissions

After a minute or so, you should have a fresh Aquarium Drunkard playlist on your Spotify account!

Once you have done this, create a `.env` file in 
 
 TBC
