from ..models import Artist, UpdaterConfig

import requests
import logging
import time

# so, in a test script, I was toying around with lastfm's API methods that could potentially work. I'd settled on using either "artist.getTopAlbums" or "artist.getInfo"
# both with pretty major tradeoffs. getTopAlbums, yes, gives me 50 of that artist's top albums, but using Jay-z as my test data it would spit out the top 7 as
# studio albums, but at "rank 8" it gave me: "Numb / Encore: MTV Ultimate Mash-Ups Presents Collision Course", which is just noise and appears before the actual
# collision course albums appears, and with no real way to see if something is a single/ep/album etc...

# getInfo returns their wiki entry (which is user generated content) and it would include the things I need (album names and their release year AND list studio albums)
# but with it being user generated, it could be wrong, outdated, or not even there. Then there's the need to actually extract that information from a massive paragraph
# and it doesn't seem consistent so can't really rely on that.

# I'm looking into using musicbrainz as an alternative and has the added benefit of not needing an API key to access it, just crazy rate limiting

# this is huge actually: "ended	| a boolean flag (true/false) indicating whether or not the artist has ended (is dissolved/deceased)" from the musicbrainz API, meaning
# I can dynamically filter for artists that aren't going to be releasing any new music because they've been dissolved in a oil drum
# nevermind, it doesn't look like they update it, searching for michael jackson shows "null" meaning either they know something I don't or it's not updated/used

API_ROOT = "https://musicbrainz.org/ws/2"

session = requests.session()
logger = logging.getLogger(__name__)

header = {
    'user-agent': 'mediamultitool (by naomisilver2002@gmail.com)' # mb's big thing is be good to the source so I'm trying to be :D
}

def fetch_artist_mbid(artist: Artist): # i kinda hated function annotations because clutter but now I'm working across multiple files with multiple functions it's quite nice
    a_name = artist.artist_name

    payload = {
        'query': a_name, # fuzzy search
        'fmt': 'json'
    }
    r = session.get(f"{API_ROOT}/artist", headers=header, params=payload)
    logger.debug(r.status_code) # for something so heavily rate limited it is very handy knowing this
    data = r.json()

    try:
        if data["artists"][0]["score"] <= 85: # mb ranks artist searches with a "confidence score", i don't think it would ever happen but prevent bad matches 
            logger.warning("Low confidence match for: %s, closest match is: %s", a_name, data["artists"][0]["name"])
            return None # nothing has changed so no need to return anything

        if data["artists"][0]["life-span"]["ended"]: # praise the lord they expose this, will probably save all albums to ended artists on the first run then
            # rarely if ever recheck
            artist.ended = True # https://www.youtube.com/watch?v=neJpZTAu-Ig (i'm slowly losing my mind)
        else: 
            artist.ended = False

        artist.mbid = data["artists"][0]["id"] 

    except IndexError as e: # for times when it doesn't return anything
        logger.error("IndexError %s when attempting to retrieve data on: %s", e, artist.artist_name)

    return artist

def fetch_artist_albums():
    pass # going to work on local caching before implementing this

def process_artist_albums(upd_cfg: UpdaterConfig, artist_data: list[Artist]):
    for artist in artist_data:
        time.sleep(1.1) # will make a more elegant rate limit solution in the future 
        logger.warning("%s | %s | %s", artist.artist_name, artist.mbid, artist.ended)
        fetch_artist_mbid(artist)
        logger.info("%s | %s | %s", artist.artist_name, artist.mbid, artist.ended)



"""
    Sources/credit:
        - musicbrainz api docs:     https://musicbrainz.org/doc/MusicBrainz_API/Search
            - it's so sad that "ended" isn't actually updated, it would've been so useful :(
            - WAIT holy shit, ended is updated 
"""