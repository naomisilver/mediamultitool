from ..models import LocalArtist, CachedArtist, UpdaterConfig
from ..core.db import Database

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

one_minute_unix_time = 60
one_hour_unix_time = 3600
one_day_unix_time = 86400 # somewhat temporary while testing
one_week_unix_time = 604800

session = requests.session()
logger = logging.getLogger(__name__)

header = {
    'user-agent': 'mediamultitool (by naomisilver2002@gmail.com)' # mb's big thing is be good to the source so I'm trying to be :D
}

def fetch_artist_mbid(a_name) -> CachedArtist: # i kinda hated function annotations because clutter but now I'm working across multiple files with multiple functions it's quite nice
    """ fetches artist mbid of a provided local artist """

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
            ended = True # https://www.youtube.com/watch?v=neJpZTAu-Ig (i'm slowly losing my mind)
        else: 
            ended = False

        artist_mbid = data["artists"][0]["id"] 

    except IndexError as e: # for times when it doesn't return anything
        logger.error("IndexError %s when attempting to retrieve data on: %s", e, a_name)

    return CachedArtist(
        artist_mbid = artist_mbid,
        artist_name = a_name,
        ended = ended
    )

def fetch_artist_albums():
    pass # going to work on local caching before implementing this

def process_local_artists(upd_cfg: UpdaterConfig, artist_data: LocalArtist):
    """ decide based on local data what to do 
    
        will get moved to a "pipeline" method when the modules get turned into classes
    """

    db = Database()
    
    for artist in artist_data:
        a = db.is_exists(artist.artist_name) # returns a CachedArtist object containing all the current DB data
        if a is None: # if not in DB
            a = fetch_artist_mbid(artist.artist_name)
            time.sleep(1.1) # RATE LIMIT I DONT WANNA GET IP BANNED BY LIKE THE ONLY 99.9% RELIABLE SOURCE FOR THIS DATA
            print(a)
            # b = fetch_artist_albums(a)
            # call fetch_albums here, get the albums from musicbrainz, split according to their release group then I get back a fully completed "CachedArtist"
            # at which point I can call db.add(b) to add it into the database. 
        
        if int(time.time()) - a.last_checked > one_week_unix_time: 
            pass # check if the current artist is outdated, if it is, call fetch_artist_album and pass in a (the retrieved artist record) and overwrite the existing
            # record doing db.add(b)

            # once all records have been updated (calling is_stale()) likely just on request, though I feel it'll happen anyway so I don't really know the best way
            # forward, but I do need some sleep 

            # then in each "if" I can make a search_mbid method in db.py using the mbid to retrieve the now updated records, compare and contrast to those locally
            # and output the missing/newest albums. Will need to isolate both updating records and doing the comparison
        
        fetch_artist_albums()

    #outdated = db.is_stale()
    
    #for o in outdated:
        #to_process.append(o)

"""
    Sources/credit:
        - musicbrainz api docs:     https://musicbrainz.org/doc/MusicBrainz_API/Search
            - it's so sad that "ended" isn't actually updated, it would've been so useful :(
            - WAIT holy shit, ended is updated 
"""