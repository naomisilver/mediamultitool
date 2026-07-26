from ..core.models import LocalArtist, CachedArtist, UpdaterConfig

from ..core.db import Database

from ..core.normalise import normalise # it was between copy the same code for this module or just "commonise" it 

from ratelimit import limits, sleep_and_retry
import requests
import logging
import time

"""

"""

API_ROOT = "https://musicbrainz.org/ws/2"

CALLS = 1 # 1 call per period
PERIOD = 1.01 # 1.01 seconds

session = requests.session()
logger = logging.getLogger(__name__)

header = {
    'user-agent': 'mediamultitool (by naomisilver2002@gmail.com)' # mb's big thing is be good to the source so I'm trying to be :D
}

@sleep_and_retry # this is awesome found from the stackoverflow link in refs
@limits(calls=CALLS, period=PERIOD) # was going to be an import script but couldn't get it working, ratelimiting each function didn't work because
# i while loop when getting albums so rate limiting a seperate helper function was the next best choice
def mb_get(path, params) -> requests.Response:
    """ rate limited get for musicbrainz """
    
    url = f"{API_ROOT}{path}"
    r = session.get(url, headers=header, params=params)

    while r.status_code == 503: # mb rate limiting avoidance
        logger.debug("Musicbrainz request failed: %s %s -> %s; body=%r", path, params, r.status_code, r.text[:100])
        time.sleep(PERIOD) # wait 1.01 seconds and try again
        r = session.get(url, headers=header, params=params)

    if r.status_code != 200 and r.status_code != 503: # mb rate limiting avoidance
        logger.warning("Musicbrainz request failed: %s %s -> %s; body=%r", path, params, r.status_code, r.text[:100])

        r.raise_for_status()

    return r

def fetch_many_artist_mbid(a_name: str) -> dict[CachedArtist]:
    """ used in fixing artists matches, returns the top X results given when querying musicbrainz """
    
    payload = {
        'query': a_name,
        'fmt': 'json'
    }
    r = mb_get("/artist", payload)

    logger.debug(r.status_code)
    data = r.json()

    artists = {}

    for i in range(5): # hardcoded for now, with headroom to let the user get the next set of artists if the 5 found aren't correct (didn't feel the need to
        try: # as out of the 300 artists in collection, 1 ended up with a bad match and didn't struggle to match within the first 5 artists found)

            if data["artists"][i]["life-span"]["ended"]:
                ended = True
            else:
                ended = False

            a_mbid = data["artists"][i]["id"]
            mb_a_name = data["artists"][i]["name"]

            try:
                a_locale = data["artists"][i]["country"]
            except KeyError as e:
                a_locale = "XW"
                logger.debug("Artist: %s, does not have a listed locale, using fallback 'XW' representing 'worldwide'", a_name)
                continue

        except IndexError as e:
            logger.error("IndexError %s when attempting to retrieve data on: %s", e, a_name)
            continue

        artists[i] =  CachedArtist(
            artist_mbid = a_mbid,
            artist_name = mb_a_name.lower(),
            artist_locale = a_locale,
            ended = ended
        )

    return artists

def fetch_artist_mbid(a_name) -> CachedArtist: # i kinda hated function annotations because clutter but now I'm working across multiple files with multiple functions it's quite nice
    """ fetches artist mbid of a provided local artist """

    payload = {
        'query': a_name, # fuzzy search
        'fmt': 'json'
    }
    r = mb_get("/artist", payload)

    logger.debug(r.status_code) # for something so heavily rate limited it is very handy knowing this
    data = r.json()

    try:
        if data["artists"][0]["score"] <= 85: # score floor for matching artists
            logger.warning("Low confidence match for: %s, closest match is: %s", a_name, data["artists"][0]["name"])
            return None # nothing has changed so no need to return anything

        if data["artists"][0]["life-span"]["ended"]: # W musicbrainz for exposing this
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
        artist_name = a_name.lower(),
        artist_locale = a_locale,
        ended = ended
    )

def fetch_artist_albums(artist: CachedArtist) -> CachedArtist:
    """ fetches and returns CachedArtist with appended albums """
    
    query = (
        f"arid:{artist.artist_mbid} AND primarytype:(album OR single OR ep) "
        #"AND NOT secondarytype:live " # I currently cache everything as new records in the local cache, it's slightly wasteful as a user who only ever checks studio_albums
        #"AND NOT secondarytype:compilation " # will never need the other 4 album types, but for one, you can't JUST query for studio albums as you can't query for the abscence 
        "AND NOT secondarytype:remix " #  of a value, only excluding the existance of a value. so I get these albums anyway. The major downside is that a query for a big artist
        "AND NOT secondarytype:interview " # may take a second or two extra
        "AND NOT secondarytype:soundtrack "
        "AND NOT secondarytype:demo "
        "AND NOT secondarytype:mixtape/street "
        #"AND NOT status:bootleg " # this didn't end up working, I don't *think* I'm getting much extra noise but I'm keeping an eye on it :D
    )

    limit = 100
    offset = 0
    score_floor = 85 # 88 still get *some* of the right albums, but < 88 has a bit too much noise, > 88 exlcudes many "best of" or "greatest hits" albums
    score_thresh = True

    while score_thresh: # continue to increase offset until the current iteration of results is below the score threshold

        payload = {
            "query": query,
            "fmt": "json",
            "limit": limit,
            "offset": offset
        }

        r = mb_get("/release-group", payload)

        data = r.json()

        for rg in data["release-groups"]:

            if rg["score"] < score_floor:
                score_thresh = False # if current score iteration is lower than the score floor, break this loop and exit while loop
                break

            title = rg["title"]
            release_group_mbid = rg["id"]

            try:
                release_date = rg["first-release-date"]
            except KeyError as e:
                continue # i shouldn't need to try catch this anymore as it was getting caught on splitting the release date, some albums have full iso 8601 date and some don't

            if rg["primary-type"].lower() != "album":
                if rg["primary-type"].lower() == "single": # singles also include singles of tracks later released in an actual album, again, idrk if I can do someting
                    # about that as some artists will release singles and NOT later release them as part of an album which is the use case I'm trying to capture
                    artist.albums.append({"release_group_mbid": release_group_mbid, "album_title": f"{normalise(title)}", "release_date": release_date, "release_type": "single"})

                if rg["primary-type"].lower() == "ep": # some eps seem to be seen as studio albums from musicbrainz and idrk if I can do anything about that
                    # and it seems to include "sessions" like aol and shit, will look into if I can set a param to ignore them
                    artist.albums.append({"release_group_mbid": release_group_mbid, "album_title": f"{normalise(title)}", "release_date": release_date, "release_type": "ep"})
                
                continue

            try:
                for st in rg["secondary-types"]:
                    if "live" in st.lower():
                        artist.albums.append({"release_group_mbid": release_group_mbid, "album_title": f"{normalise(title)}", "release_date": release_date, "release_type": "live_album"})

                    if "compilation" in st.lower():
                        artist.albums.append({"release_group_mbid": release_group_mbid, "album_title": f"{normalise(title)}", "release_date": release_date, "release_type": "compilation"})

            except KeyError:
                artist.albums.append({"release_group_mbid": release_group_mbid, "album_title": f"{normalise(title)}", "release_date": release_date, "release_type": "studio_album"})

        count = data["count"] # if the count value indicating the amount of results isn't present, break after the first cycle as theres no pages to ination xD
        if count is None:
            break

        offset += limit # if it finds only scores higher than score_floor and the offset exceeds the total count it can break
        if offset >= count:
            break
    
    return artist      

"""
    Sources/credit:
        - musicbrainz api docs:             https://musicbrainz.org/doc/MusicBrainz_API/Search
            - it's so sad that "ended" isn't actually updated, it would've been so useful :(
            - WAIT holy shit, ended is updated 
        - musicbrianz pagination:           https://community.metabrainz.org/t/api-browse-and-paging/814161
        - musicbrainz lucene query:         https://community.metabrainz.org/t/how-do-i-get-just-the-studio-albums-from-an-artist/461554/7
        - lots of staring at:               https://musicbrainz.org/ws/2/release-group?query=arid:4ebb5ad3-9018-407d-8c24-c03011ab9ac6%20primarytype:album%20NOT%20secondarytype:live%20NOT%20secondarytype:compilation%20NOT%20secondarytype:remix%20NOT%20secondarytype:interview%20NOT%20secondarytype:soundtrack&fmt=json    
        - ratelimit:                        https://stackoverflow.com/questions/40748687/python-api-rate-limiting-how-to-limit-api-calls-globally
                                            https://pypi.org/project/ratelimit/
"""