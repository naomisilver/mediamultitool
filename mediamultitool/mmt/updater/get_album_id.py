import requests
import logging
from ratelimit import limits, sleep_and_retry

DEEZER_API_ROOT = "https://api.deezer.com/"
DEEZER_CALLS = 50
DEEZER_PERIOD = 5.01

session = requests.session()
logger = logging.getLogger(__name__)

HEADER = {
    'user-agent': 'mediamultitool (by naomisilver@gmail.com)'
}

@sleep_and_retry
@limits(calls=DEEZER_CALLS, period=DEEZER_PERIOD) # deezer is limited to 50 requests every 5 seconds, i don't expect to reach that though
def deezer_get(path, payload):
    """ rate limited get for deezer """
    
    url = f"{DEEZER_API_ROOT}{path}"
    r = session.get(url, headers=HEADER, params=payload)

    if r.status_code != 200:
        logger.warning("Deezer request failed: %s %s -> %s; body=%r", path, payload, r.status_code, r.text[:100])

        r.raise_for_status()

    return r

def get_deezer_artist_id(artist_name: str, i: int):
    """ fuzzy search for artist id (no confidence scoring here so likely same issues I was going to if
    i used last.fm, I think I will use some album matching, if selected artist's albums match any of those
    in missing, then it's the right match, otherwise call again to fetch the correct one) 
    """
    
    payload = {
        'q': artist_name,
        'limit': 5,
        'output': 'json'
    }

    r = deezer_get("/search/artist", payload)
    data = r.json()

    try:
        artist_id = data["data"][i]["id"]
        return artist_id
    except KeyError:
        logger.error("Found no artists of name: %s", artist_name)
    except IndexError:
        logger.error("Found no viable match for %s", artist_name)
    
    return None

def get_deezer_album_id(artist_id: int, index: int) -> dict[str, str]:
    """ once we got the artist id we can grab the albums of that artist """
    
    payload = {
        'limit': 1000, # deezer doesn't seem to have a listed limit to what they can return but does have a "query quota" but it isn't listed anywhere
        'index': index, # they do limit to 50 queries every 5 seconds which i rate limit for but yeah, idk 
        'output': 'json'
    }

    albums = {}

    r = deezer_get(f"/artist/{artist_id}/albums", payload)
    data = r.json()

    for album in data["data"]:

        albums[album["title"].lower()] = {
            "album_id":  album["id"],
            "explicit_lyrics": album["explicit_lyrics"],
            "release_date": album["release_date"],
            "record_type": album['record_type']
        }

    return albums

def get_fuzzy_deezer_album_id(album_name: str, artist_name: str):
    """ fuzzy query for album id using album and artist name if it isn't found when querying artist albums """

    payload = {
        'q': f'{album_name} {artist_name}',
        'limit': 100,
        'output': 'json'
    }

    albums = []

    r = deezer_get(f"/search/album", payload)
    data = r.json()
    try:
        for album in data["data"]:

            albums.append({
                "album_id": album['id'],
                "title": album['title'],
                "explcit_lyrics": album['explicit_lyrics'],
                "record_type": album['record_type'],
                "artist_id": album['artist']['id'],
                "artist_name": album['artist']['name']
            })
    except KeyError:
        logger.error("No results for %s: %s", artist_name, album_name)

    return albums

def get_album_name_from_id(id: int) -> str:
    """ exists entirely to check which albums get found for debugging """

    payload = {
        'limit': 1,
        'output': 'json'
    }

    r = deezer_get(f"/album/{id}", payload)
    data = r.json()

    try:
        return (data["title"], data["record_type"])
    except KeyError:
        return None

"""
https://api.deezer.com/search/artist/?q=eminem
https://api.deezer.com/artist/13/albums?limit=500&index=0

there doesn't seem to be a limit to how much I can get back in a single query which is nice
"""