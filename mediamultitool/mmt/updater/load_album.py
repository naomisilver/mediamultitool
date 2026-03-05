from ..models import LocalArtist, CachedArtist, UpdaterConfig

from .get_albums import fetch_artist_albums, fetch_artist_mbid

from ..core.normalise import normalise
from ..core.db import Database

from pathlib import Path
import logging
import re
import time

logger = logging.getLogger(__name__)

"""
TODO:
    - there's some things to consider like:
        - allowing the user to search for only the given artists through the cli, e.g., "mmt updater -only blink-182 YOASOBI"
        - allowing the user to search ignoring the given artists through the cli, e.g., "mmt updater -exlcuding blink-182 YOASOBI"
        - then in config:
            - allowing the user to define a list of "always ignore" list so they don't need to repeatedly add the same artists as args

    - downloading is going to be a beast on its own, my absolute best bet would be to look at using streamrip though their "scripting with streamrip" wiki page
      is woefully lacking, it allows searching using a metadata tag but not sure what that metadata represents, last.fm albumID? qobuz? idk but I could really do
      with using their search functionality to find it, otherwise I'm kinda boned
"""

one_minute_unix_time = 60
one_hour_unix_time = 3600
one_day_unix_time = 86400 # somewhat temporary while testing
one_week_unix_time = 604800
one_month_unix_time = 2629743
one_year_unix_time = 31556926

def regex_tag_check(s: str) -> int:
    """ helper to find the release year of a given album """

    tags = re.findall("\([1-2][0-9][0-9][0-9]\)", s) # easy change to only accept numbers from 1000-2999 as apposed to 0000-9999

    newest_tag = 0

    for tag in tags:
        if len(tags) == 1: # using regex ive yet to be given more than 1 tag that matches, but if at any point theres more, I can look at the two tags and create rules for that
            # kinda hard to write catches for data I don't know of
            return int(tag.replace("(", "").replace(")", ""))
        
        if len(tags) >= 2:
            if newest_tag == 0:
                newest_tag = tag
            
            if tag > newest_tag:
                newest_tag = tag

            return int(newest_tag.replace("(", "").replace(")", ""))
        
        else:
            logger.error("Found multiple potential tag matches: %s, please open an issue showing this message.", s)

def normalise_album(s: str) -> str: 
    """ helper to generalise a given album e.g., "(1999), (Live)" etc """

    s = s.split(" - ", 1)[-1].split("(", 1)[0].strip()

    return s

def get_newest_album(upd_cfg: UpdaterConfig) -> LocalArtist:
    """ retrieve artists and their latest albums """

    music_path = upd_cfg.local_music_path
    artist_data = []

    for artist in music_path.iterdir():
        if artist.name.lower() == ("various artists", "playlist"):
            print("hello")
            continue # don't want to be attempting to download tracks from various artists, that would 100% bite me in the ass if I did...

        artist_name = artist.name

        all_albums = [Path(x).name for x in artist.iterdir()]

        newest_album = ""
        newest_album_year = 0

        for album in all_albums:
            if not newest_album: # on first album, assign the first one as the latest
                newest_album = album 
                newest_album_year = regex_tag_check(newest_album)
                continue

            try: # I would get errant TypeErrors saying that None cannot be used alongside the greater than operator and can't place why yet
                if regex_tag_check(album) > newest_album_year: # if album is newest, save
                    newest_album = album
                    newest_album_year = regex_tag_check(album)
                    continue

            except TypeError as e:
                logger.error("TypeError, %s attempting to compare %s to %s. Source: %s", e, regex_tag_check(album), newest_album_year, album)

        artist_data.append(LocalArtist(
            artist_name = artist_name,
            latest_album = f"{normalise(normalise_album(album))} ({regex_tag_check(album)})", # before adding to the Artist object, I could really do with normalising/generalising it similar to playlist, though I really don't feel like
            # mirroring the same logic so will look at how I could handle it using regex. 
            all_albums = [f"{normalise(normalise_album(album))} ({regex_tag_check(album)})" for album in all_albums] # god I love list comprehension
        )) # in my test script, I retained the release year in the as it should help to give another way to match data later

    process_local_artists(upd_cfg, artist_data)

def compare_albums(upd_cfg: UpdaterConfig, db_items: list, local_artist: LocalArtist) -> list:
    #list(albums) # if newest album gets passed just ensure it is a list
    
    if upd_cfg.all_or_new: # if it is "all"/"ALL" ONLY then treat all all
        missing = [x for x in db_items if x not in local_artist.all_albums]
        return missing
    
    else: # treat everything else as only checking new 
        missing = []

        local_year = regex_tag_check(local_artist.latest_album)
        for i in db_items:
            db_year = regex_tag_check(i)

            if db_year > local_year:
                missing.append(i)

        return missing

def process_local_artists(upd_cfg: UpdaterConfig, local_artist_data: LocalArtist):
    """ decide based on local data what to do 
    
        will get moved to a "pipeline" method when the modules get turned into classes
    """

    t = int(time.time())

    db = Database()
    
    for local_artist in local_artist_data: # add new if it doesn't exist
        a = db.is_exists(local_artist.artist_name) # returns a CachedArtist object containing all the current DB data 
        if a is None: # if not in DB
            #time.sleep(1.1)

            a = fetch_artist_mbid(local_artist.artist_name)
            logger.info("%s", a)

            #time.sleep(1.1) # RATE LIMIT I DONT WANNA GET IP BANNED BY LIKE THE ONLY 99.9% RELIABLE SOURCE FOR THIS DATA

            b = fetch_artist_albums(a)
            logger.error("%s: %s", b.artist_name, b.studio_albums)

            db.add(b)

    stale_artists = db.is_stale()
    for stale_a in stale_artists:
        if bool(stale_a.ended) is True and t - stale_a.last_checked < one_year_unix_time: # if ended & last checked less than a year ago
            logger.debug("Skipping updating artist %s, ended and last checked < a year ago", stale_a.artist_name)
            continue

        if stale_a.ended is not True and t - stale_a.last_checked < one_week_unix_time: # if not & last checked less than a week ago 
            logger.debug("Skipping updating artist %s, last checked < a week ago", stale_a.artist_name)
            continue

        updated_a = fetch_artist_albums(stale_a)

        logger.info("Updated artist: %s", updated_a.artist_name)

        db.add(updated_a)

    for local_artist in local_artist_data:
        db_artist = db.is_exists(local_artist.artist_name)

        for album_type, ignore in upd_cfg.ignore.items():
            if ignore:
                continue

            db_items = getattr(db_artist, album_type)
            
            missing = compare_albums(upd_cfg, db_items, local_artist) # not perfect, need to dive deeper, though, slay the spire 2 came out 4 minutes ago
            if not missing: # and I NEEED to jump on that :)
                continue

            logger.warning("Missing albums for artist %s: %s", local_artist.artist_name, missing)

"""
    Sources/credit:
        - regex:    https://www.w3schools.com/python/python_regex.asp
                    https://www.geeksforgeeks.org/python/check-for-balanced-parentheses-in-python/
                    - I'm finally biting the bullet and I have a feeling this regex sources section is going to get pretty large... 

        - compare 2 lists, output missing   https://stackoverflow.com/questions/78488469/sqlite-insert-or-replace-and-on-conflict-do-nothing 
"""