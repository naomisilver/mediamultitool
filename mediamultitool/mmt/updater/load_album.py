from ..core.models import LocalArtist, CachedArtist, UpdaterConfig
from ..core.richui import RichUI 

from .get_albums import fetch_artist_albums, fetch_artist_mbid, fetch_many_artist_mbid
from .download_albums import get_source

from ..core.normalise import normalise
from ..core.db import Database

from pathlib import Path
from platformdirs import user_config_dir
import logging
import re
import time
import os
import json
from datetime import datetime, date
from rich import print, box
from rich.console import Console
from rich.table import Table, Column
from rich.prompt import Prompt
from rich.live import Live

logger = logging.getLogger(__name__)

"""

"""

def regex_tag_check(s: str) -> int:
    """ helper to find the release year of a given album """

    tags = re.findall(r'\([1-2][0-9][0-9][0-9]\)', s) # im assuming since moving to linux I'm using a newer python version (3.13.7 vs 3.11.9) this giving a syntax warning claiming
    # "\(" wasn't a valid escape sequence, it still worked but printed the warning, using a raw string fixed that

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
    s = s.replace("-", " ")

    return s

def parse_partial_date(s: str) -> date:
    """ helper to normalise when musicbrainz gives only year or year-month """

    parts = s.split("-") # YEAR-MONTH-DAY / 2000-01-01

    year = int(parts[0])
    month = int(parts[1]) if len(parts) > 1 else 1
    day = int(parts[2]) if len(parts) > 2 else 1 # makes just the year "2000" return as "2000-1-1" so i can compare dates against each other

    return date(year, month, day)

def get_newest_album(upd_cfg: UpdaterConfig, excluded_list: list, only_list: list) -> LocalArtist:
    """ retrieve artists and their latest albums """

    music_path = upd_cfg.local_music_path
    artist_data = []

    for artist in music_path.iterdir():
        artist_name = artist.name.lower()
        if only_list:
            if artist_name not in only_list:
                continue

        if artist_name in excluded_list:
            continue # don't want to be attempting to download tracks from various artists, that would 100% bite me in the ass if I did...

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
            latest_album = f"{normalise(normalise_album(newest_album))} ({regex_tag_check(newest_album)})", # i had this as album for so long and not newest_album :|
            all_albums = [f"{normalise(normalise_album(album))} ({regex_tag_check(album)})" for album in all_albums] # god I love list comprehension
        )) # in my test script, I retained the release year in the as it should help to give another way to match data later

    process_local_artists(upd_cfg, artist_data)

def compare_albums(upd_cfg: UpdaterConfig, db_items: list, local_artist: LocalArtist) -> list:

    if upd_cfg.all_or_new: # use only the name of the chached db album and substring match to local albums
        local_titles = [normalise(a.split("(")[0]) for a in local_artist.all_albums]

        missing = []

        for x in db_items:
            db_title = normalise_album(normalise(x['album_title']))#.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
            db_year = x['release_date'].split('-')[0]

            #if db_title not in local_titles:
            if not any(db_title in lt or lt in db_title for lt in local_titles): # this is not really "safe" matching as any instance of either local or cache album names
                missing.append(f"{db_title} ({db_year})") # will be used to match, and situations like "One More Time... PART 2" would match with "One More Time" where PART 2 dropped
                # new tracks, I could match only local titles to cache titles but because I deal with release-groups and not releases (for very good reason), I would need to peform a
                # thousand lines of normalisation to get even close to a "safer" match

        return missing
    
    else: # ignores the name of the album and uses only the year to compare. this isn't ideal as someone may release 3 studio albums in a year and if the newest locally is the first
        missing = [] # of those 3, it misses the other two. the alternative would be querying musicbrainz to get the release list and compare local to that. Or save a list of the release
        # order when cacheing locally. That would mean another table and saving the list in order

        local_year = regex_tag_check(local_artist.latest_album)
        for item in db_items:
            db_year = regex_tag_check(f"({item['release_date'].split("-")[0]})")

            try:
                if db_year > local_year:
                    missing.append(f"{item['album_title']} ({db_year})")
            except TypeError: # I hadn't checked the edge case of just an artist directory with no albums inside
                missing.append(f"{item['album_title']} ({db_year})") # would fail because there's no album to check it against

        return missing

def update_cache(local_artist_data: LocalArtist, db: Database, ui: RichUI): # unsure whether I should include this here or move to a seperate file, will sleep on it
    """ scans local collection, and updates local cache, based on existance/last_checked, from musicbrainz """
    
    #ui = RichUI()
    #ui.start()

    index = 1

    t = int(time.time())
    
    for local_artist in local_artist_data: # add new if it doesn't exist
        if not db.is_exists(local_artist.artist_name.lower()):

            mb_artist = fetch_artist_mbid(local_artist.artist_name)
            logger.debug("Found artist %s with the mbid: %s", mb_artist.artist_name, mb_artist.artist_mbid)

            mb_artist = fetch_artist_albums(mb_artist)
            logger.debug("Found %s albums for artist: %s", len(mb_artist.albums), mb_artist.artist_name)

            total = len(local_artist_data)
            index = index + 1
            count = f"{index}/{total}"
            ui.artist_albums_updated(mb_artist, count)

            db.add(mb_artist)

    stale_artists = db.is_stale()
    for stale_a in stale_artists:

        updated_a = fetch_artist_albums(stale_a)

        total = len(stale_artists)
        index = index + 1
        count = f"{index}/{total}"
        ui.artist_albums_updated(updated_a, count)

        db.add(updated_a)

    #ui.stop()

def delete_local_missing(upd_cfg: UpdaterConfig, db: Database):
    """ removes artists no longer present in local collection and removes them from local cache """

    db_artists = db.retrieve_artist_names()
    local_artists = [Path(x).name.lower() for x in upd_cfg.local_music_path.iterdir()]

    local_missing = list(set(db_artists) - set(local_artists))

    if local_missing:
        logger.info("Found %s missing locally, removing from local cache", len(local_missing))
        db.remove(local_missing)

def add_db_missing(upd_cfg: UpdaterConfig, db: Database):
    """ takes new artists in local collection to add to local cache """

    db_artists = db.retrieve_artist_names()
    local_artists = [Path(x).name.lower() for x in upd_cfg.local_music_path.iterdir()]

    db_missing = list(set(local_artists) - set(db_artists))
    db_missing = set(db_missing) - set(upd_cfg.excluded_artists) # it wouldn't exclude the artists defined in config otherwise

    if db_missing:
        logger.info("Found %s new artists, updating local cache", len(db_missing))
        return True

    return False

def process_local_artists(upd_cfg: UpdaterConfig, local_artist_data: LocalArtist):
    """ decide, based on local data, what to do 
    
        will get moved to a "pipeline" method when the modules get turned into classes
    """

    db = Database(upd_cfg.db_path)
    ui = RichUI()
    ui.start()

    delete_local_missing(upd_cfg, db) # happen before updating so its not querying mb for soon to be deleted data

    stale_artists = db.is_stale()
    if stale_artists:
        logger.info("You have %s outdated artists, you may want to run 'mmt updater --update-cache'", len(stale_artists))
    
    if upd_cfg.update_cache or add_db_missing(upd_cfg, db): # this can be done better when I move each module to a class, this can be called/run the require logic from main
        update_cache(local_artist_data, db, ui)
    elif os.path.isfile(upd_cfg.db_path):
        pass
    else:
        logger.error("The local cache has not yet been created, please run 'mmt updater -update-cache to generate cache")
        raise SystemExit
    
    missing_albums = {}

    for local_artist in local_artist_data:
        db_artist = db.retrieve_albums(local_artist.artist_name.lower())

        missing_albums[local_artist.artist_name] = {} # accidently recreating the dictionary item every iteration so would end up 
        # only with the 
        for album_type, ignore in upd_cfg.ignore.items():
            if ignore:
                continue

            d = date.today()

            db_items = [album for album in db_artist.albums if album["release_type"] == album_type and d >= parse_partial_date(album["release_date"])]

            missing = compare_albums(upd_cfg, db_items, local_artist)
            if not missing:
                continue

            # only used in writing to a json file, kind of a stopgap until downloading is implemented
            missing_albums[local_artist.artist_name][f"{album_type}s"] = missing # then -d/--download would output the small table and write the json file
            # downloader.py would then take over, using the most recent json file as the stock to download from

            if upd_cfg.output_to_console:
                logger.debug("Missing %s %ss for artist %s: %s", len(missing), album_type, local_artist.artist_name, missing)
                ui.updater_missing_albums_all(local_artist.artist_name, missing, album_type)
                # a quirk of this implementation is that when printing the missing table with more than one album type not ignored (e.g., studio_albums and eps)
                # it outputs both as induvidual rows and I think that is the best way, that way it's clear that I'm mising say 1 studio album from the rolling stones
                # and 136 eps rather than it appearing as i'm missing 137 albums total (that's a real comparison, what were the rolling stones smoking)
            else:
                logger.debug("Missing %s %ss for artist %s: %s", len(missing), album_type, local_artist.artist_name, missing)
                ui.updater_missing_albums_one(local_artist.artist_name, missing, album_type)

    ui.stop()

    missing_albums = {k: v for k, v in missing_albums.items() if v} # efficient "empty" dict items https://stackoverflow.com/questions/12118695/efficient-way-to-remove-keys-with-empty-strings-from-a-dict
    # moving the dict key declaration out of the loop, it now generates the key even if there is no missing albums of any type 

    if upd_cfg.download:
        get_source(upd_cfg, missing_albums)

    elif not upd_cfg.output_to_console:
        write_output_to_json(upd_cfg, missing_albums)

def write_output_to_json(upd_cfg: UpdaterConfig, missing_albums: dict[str: list[str]]):
    """ writes the given dict to json file """
    
    json_filename = str(datetime.now())
    json_filename = json_filename.replace(":", "-")
    json_path = Path(upd_cfg.output_dir / f"{json_filename[:19]}.json")
    with open(json_path, "w") as f:
        json.dump(missing_albums, f, indent=4, ensure_ascii=False)

    logger.info("Written missing albums to '%s'", json_path)

def fix_artist_match(artist_name: list, upd_cfg: UpdaterConfig):
    """ takes user input on a bad match and presents other potential fixes """
    
    db = Database(upd_cfg.db_path)
    con = Console()

    ui = RichUI()
    ui.start()

    if db.is_exists(''.join(artist_name)): # rather than converting the input list to a string in main, I'm passing the list because remove expects a list and it's messier to convert
        db_artist = db.retrieve_albums(''.join(artist_name)) # back to a list than it is to convert a single item list to a string

        ui.static_artist_details(db_artist)
        ui.stop()

        artists = {}

        ui.artist_rows = []
        
        ans = ui.ask("[bold green]Is this the record you wish to delete and refresh? [Y/n][/bold green]").lower()
        if ans in ["y", "yes"]:
            db.remove(artist_name)

            artists = fetch_many_artist_mbid(''.join(artist_name))

            for index, artist in artists.items():
                artists[index] = fetch_artist_albums(artist)

                ui.start() # not exactly elegant but because i use live to render my tables, when trying to print without explicitly starting and
                ui.static_artist_details(artists[index], f"[{index + 1}] {artists[index].artist_name}") # stopping the live rendering, the "is this right" table would prevent rendering the next tables
                ui.stop() # I *could* completely refactor richui to handles this automatically but i fear adding 3 method calls is far easier and simpler

            ans = ui.ask("[bold green]Please select the number that matches the artist you wish to replace [1-5][/bold green]")
            ans = int(ans)
            db.add(artists[ans - 1])

        else:
            print("[bold red]aborted![/bold red]")
    else:
        logger.warning("%s does not exist in local cache", str(artist_name))


"""
    Sources/credit:
        - regex:    https://www.w3schools.com/python/python_regex.asp
                    https://www.geeksforgeeks.org/python/check-for-balanced-parentheses-in-python/
                    - I'm finally biting the bullet and I have a feeling this regex sources section is going to get pretty large... 

        - compare 2 lists, output missing https://stackoverflow.com/questions/78488469/sqlite-insert-or-replace-and-on-conflict-do-nothing... idrk what this is in relation to
          but I went to compare 2 lists again and used this: https://www.geeksforgeeks.org/python/python-difference-two-lists/ for set difference

        - not converting unicode to unicode escape sequences: https://docs.python.org/3/library/json.html
            - kinda sucks when you're dealing with cyrillic, japanese etc... album names

        - iso 8601 vs iso 8601:             https://www.influxdata.com/blog/python-date-comparison-comprehensive-tutorial/
"""