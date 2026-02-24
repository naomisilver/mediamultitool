from ..models import LocalArtist, CachedArtist, UpdaterConfig
from ..core.db import Database

from ..core.normalise import normalise # it was between copy the same code for this module or just "commonise" it 

import requests
import logging
import time

"""
    - TODO:
        - Implement something to scroll another page even after the "score_thresh" flag is triggered to see if that can help capture any missed releases and allowing
          me to increase the score_floor to weed out some of the noise

        - see if there's anything I can do to exlcude track single releases that later end up in an album so that only the unique singles stick (i fear I won't be able
          to do much as I don't think that information will be exposed by musicbrainz)

        - some EPs are shown to be a studio album release AND an ep so my current setup capture both and place them both in, not necessarily a massive issue but I need
          to see how prolific it is, if there's nothing I can do in the fetch_album func, I should be able to check if it's in EP then I can remove it from studio_albums

        - now that *I think* I'm capturing all of the necessary album data, I can look to finally add it to the database then make the function to actually compare
          local albums to those found in the db cache

        - way later down the line, I then need to make the many options, well, optional. That is the ignores for EPs, singles, compilations, lives and I will likely
          add remixes to the cache. Then I would like to add the ability for users to define the score_floor value so they can fine tune it to their libary. 

        - add a more precise rate limiting function so that I can really squeeze out that extra 100ms from the current time.sleep

        - stretch goal for this branch is to add the ability to remap certain artist/mbid matchups. I don't think any of my current 300+ artists have had a mismatch
          (aside from "F.U.N" because locally it's "FUN") where it either takes current albums from a given artist, searches to see if those albums belond to any of
          the get_mbid artists and picks the right one, or present the user with a list of potential matches, and some of their studio albums to pick from, then update
          the local record and wipes the record for that particular artist
"""

API_ROOT = "https://musicbrainz.org/ws/2"

one_minute_unix_time = 60
one_hour_unix_time = 3600
one_day_unix_time = 86400 # somewhat temporary while testing
one_week_unix_time = 604800
one_month_unix_time = 2629743
one_year_unix_time = 31556926

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

        a_mbid = data["artists"][0]["id"]

        try:
            a_locale = data["artists"][0]["country"]
        except KeyError as e:
            a_locale = "XW"
            logger.debug("Artist: %s, does not have a listed locale, using fallback 'XW' representing 'worldwide'", a_name)

    except IndexError as e: # for times when it doesn't return anything
        logger.error("IndexError %s when attempting to retrieve data on: %s", e, a_name)

    return CachedArtist(
        artist_mbid = a_mbid,
        artist_name = a_name,
        artist_locale = a_locale,
        ended = ended
    )

def fetch_artist_albums(artist: CachedArtist) -> CachedArtist:
    """ fetches and returns CachedArtist with appended albums """

    artist.studio_albums = []
    artist.eps = []
    artist.singles = [] # no longer appending to an existing list of existing albums and causing duplicates
    artist.compilations = []
    artist.live_albums = []

    query = (
        f"arid:{artist.artist_mbid} AND primarytype:(album OR single OR ep) "
        #"AND NOT secondarytype:live "
        #"AND NOT secondarytype:compilation "
        "AND NOT secondarytype:remix "
        "AND NOT secondarytype:interview "
        "AND NOT secondarytype:soundtrack "
        "AND NOT secondarytype:demo "
        "AND NOT secondarytype:mixtape/street "
        #"AND NOT status:bootleg "
    )

    limit = 100
    offset = 0
    score_floor = 85 # 88 still get *some* of the right albums, but < 88 has a bit too much noise, > 88 exlcudes many "best of" or "greatest hits" albums, need to
    # try and see if the json data is not sequentially given in terms of the score, maybe a score 75 is listed above a 90 and so I break too soon to capture that
    score_thresh = True

    while score_thresh: # continue to increase offset until the current iteration of results is below the score threshold

        time.sleep(1.1)

        payload = {
            "query": query,
            "fmt": "json",
            "limit": limit,
            "offset": offset
        }

        r = session.get(f"{API_ROOT}/release-group", headers=header, params=payload)
        data = r.json()

        for rg in data["release-groups"]:

            if rg["score"] < score_floor:
                score_thresh = False # if current score iteration is lower than the score floor, break this loop and exit while loop
                break

            title = rg["title"]
            try:
                release_year = rg["first-release-date"].split("-", 1)[0]
            except KeyError as e:
                continue # this was causing some weird behaviour, specifically for the band "american football", it would find an album "all of us" that doesn't exist
            # when I pull the same data from the same url it'd be using, so instead skip instances of this. 

            if rg["primary-type"].lower() != "album":
                if rg["primary-type"].lower() == "single": # singles also include singles of tracks later released in an actual album, again, idrk if I can do someting
                    # about that as some artists will release singles and NOT later release them as part of an album which is the use case I'm trying to capture
                    artist.singles.append(f"{normalise(title)} ({release_year})")

                if rg["primary-type"].lower() == "ep": # some eps seem to be seen as studio albums from musicbrainz and idrk if I can do anything about that
                    # and it seems to include "sessions" like aol and shit, will look into if I can set a param to ignore them
                    artist.eps.append(f"{normalise(title)} ({release_year})")
                
                continue

            try:
                for st in rg["secondary-types"]:
                    if "live" in st.lower():
                        artist.live_albums.append(f"{normalise(title)} ({release_year})")
                    if "compilation" in st.lower():
                        artist.compilations.append(f"{normalise(title)} ({release_year})")

            except KeyError: # if secondary-types doesn't exist then it has to be a studio album
                artist.studio_albums.append(f"{normalise(title)} ({release_year})")

        count = data["count"] # if the count value indicating the amount of results isn't present, break after the first cycle as theres no pages to ination XD
        if count is None:
            break

        offset += limit # if it finds only scores higher than score_floor and the offset exceeds the total count it can break
        if offset >= count:
            break

        #time.sleep(1.1)
    
    return artist


def process_local_artists(upd_cfg: UpdaterConfig, local_artist_data: LocalArtist):
    """ decide based on local data what to do 
    
        will get moved to a "pipeline" method when the modules get turned into classes
    """

    t = int(time.time())

    db = Database()
    
    for local_artist in local_artist_data: # add new if it doesn't exist
        a = db.is_exists(local_artist.artist_name) # returns a CachedArtist object containing all the current DB data 
        if a is None: # if not in DB
            time.sleep(1.1)

            a = fetch_artist_mbid(local_artist.artist_name)
            logger.info("%s", a)

            time.sleep(1.1) # RATE LIMIT I DONT WANNA GET IP BANNED BY LIKE THE ONLY 99.9% RELIABLE SOURCE FOR THIS DATA

            b = fetch_artist_albums(a)
            logger.error("%s: %s", b.artist_name, b.studio_albums)

            db.add(b)

    stale_artists = db.is_stale()
    for stale_a in stale_artists:
        if stale_a.ended is True and t - stale_a.last_checked < one_year_unix_time: # if ended & last checked less than a year ago
            logger.debug("Skipping artist %s, ended and last checked < a year ago")
            continue

        if stale_a.ended is not True and t - stale_a.last_checked < one_minute_unix_time: # if not & last checked less than a week ago 
            logger.debug("Skipping artist %s, last checked < a week ago")
            continue

        updated_a = fetch_artist_albums(stale_a)

        logger.info("Updated artist: %s", updated_a.studio_albums)

        db.add(updated_a)

    for local_artist in local_artist_data:
        db_artist = db.is_exists(local_artist.artist_name)

        temp3 = [x for x in db_artist.studio_albums if x not in local_artist.all_albums]

        logger.warning("Missing albums for artist %s are: %s", local_artist.artist_name, temp3)


"""
    Sources/credit:
        - musicbrainz api docs:             https://musicbrainz.org/doc/MusicBrainz_API/Search
            - it's so sad that "ended" isn't actually updated, it would've been so useful :(
            - WAIT holy shit, ended is updated 
        - musicbrianz pagination:           https://community.metabrainz.org/t/api-browse-and-paging/814161
        - musicbrainz lucene query:         https://community.metabrainz.org/t/how-do-i-get-just-the-studio-albums-from-an-artist/461554/7
        - lots of staring at:               https://musicbrainz.org/ws/2/release-group?query=arid:4ebb5ad3-9018-407d-8c24-c03011ab9ac6%20primarytype:album%20NOT%20secondarytype:live%20NOT%20secondarytype:compilation%20NOT%20secondarytype:remix%20NOT%20secondarytype:interview%20NOT%20secondarytype:soundtrack&fmt=json
        - compare 2 lists, output missing   https://stackoverflow.com/questions/78488469/sqlite-insert-or-replace-and-on-conflict-do-nothing     
"""