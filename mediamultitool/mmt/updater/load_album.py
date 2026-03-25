from ..core.models import LocalArtist, CachedArtist, UpdaterConfig
from ..core.richui import RichUI 

from .get_albums import fetch_artist_albums, fetch_artist_mbid, fetch_many_artist_mbid

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
TODO:
    - Look at a more elegant way to handle user interaction for 'fix_artist_match', I'm going to look into click as an alternative to argparse
      as it has user input prompts built-in which is nice and then rich as a potential option for stdout. Rich also has progress bars which would spice
      up the long waits for querying mb. Can replace outputting every found artist for a loading bar showing the most recent downloaded
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

    parts = s.split("-")

    year = int(parts[0])
    month = int(parts[1]) if len(parts) > 1 else 1
    day = int(parts[2]) if len(parts) > 2 else 1

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

            if db_year > local_year:
                missing.append(f"{item['album_title']} ({db_year})")

        return missing
    
def make_table(rows):
    table = Table()
    table.add_column("Artist name")
    table.add_column("MBID")

    for r in rows:
        table.add_row(*r)

    return table

def update_cache(local_artist_data: LocalArtist, db: Database): # unsure whether I should include this here or move to a seperate file, will sleep on it
    """ scans local collection, and updates local cache, based on existance/last_checked, from musicbrainz """
    
    ui = RichUI()
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

    if db_missing:
        logger.info("Found %s new artists, updating local cache", len(db_missing))
        return True

    return False

def process_local_artists(upd_cfg: UpdaterConfig, local_artist_data: LocalArtist):
    """ decide, based on local data, what to do 
    
        will get moved to a "pipeline" method when the modules get turned into classes
    """

    db = Database(upd_cfg.db_path)

    delete_local_missing(upd_cfg, db) # happen before updating so its not querying mb for soon to be deleted data

    stale_artists = db.is_stale()
    if stale_artists:
        logger.info("You have %s outdated artists, you may want to run 'mmt updater --update-cache'", len(stale_artists))
    
    if upd_cfg.update_cache or add_db_missing(upd_cfg, db): # this can be done better when I move each module to a class, this can be called/run the require logic from main
        update_cache(local_artist_data, db)
    elif os.path.isfile(upd_cfg.db_path):
        pass
    else:
        logger.error("The local cache has not yet been created, please run 'mmt updater -update-cache to generate cache")
        raise SystemExit
    
    missing_albums = {}

    for local_artist in local_artist_data:
        db_artist = db.retrieve_albums(local_artist.artist_name.lower())

        for album_type, ignore in upd_cfg.ignore.items():
            if ignore:
                continue

            d = date.today()

            db_items = [album for album in db_artist.albums if album["release_type"] == album_type and d >= parse_partial_date(album["release_date"])]

            missing = compare_albums(upd_cfg, db_items, local_artist)
            if not missing:
                continue

            missing_albums[local_artist.artist_name] = {}
            missing_albums[local_artist.artist_name][f"{album_type}s"] = missing

            if upd_cfg.output_to_console:
                logger.warning("Missing %s %ss for artist %s: %s", len(missing), album_type, local_artist.artist_name, missing)

            elif len(missing) <= 2:
                logger.warning("Missing %s %ss for artist %s: %s", len(missing), album_type, local_artist.artist_name, missing)

            elif len(missing) > 2:
                logger.warning("Missing %s %ss for artist %s: %s + %s more", len(missing), album_type, local_artist.artist_name, missing[:2], len(missing) - 2)

    if not upd_cfg.output_to_console:
        write_output_to_json(upd_cfg, missing_albums)

def write_output_to_json(upd_cfg: UpdaterConfig, missing_albums: dict[str: list[str]]):
    """ writes the given dict to json file """
    
    json_filename = str(datetime.now())
    json_path = Path(upd_cfg.output_dir / f"{json_filename[:19]}.json")
    with open(json_path, "w") as f:
        json.dump(missing_albums, f, indent=4, ensure_ascii=False)

    logger.info("Written missing albums to '%s'", json_path)

def fix_artist_match(artist_name: list, upd_cfg: UpdaterConfig):
    """ takes user input on a bad match and presents other potential fixes """
    
    db = Database(upd_cfg.db_path)
    con = Console()

    priority = {
        "studio_album": 4,
        "ep": 3, # reverse order as my dates are iso 8601 format and have to reverse them to get studio album > ep > single with most recent first
        "single": 2,
        "compilation": 1,
        "live_album": 0,

    }

    if db.is_exists(''.join(artist_name)): # rather than converting the input list to a string in main, I'm passing the list because remove expects a list and it's messier to convert
        db_artist = db.retrieve_albums(''.join(artist_name)) # back to a list than it is to convert a single item list to a string

        table = Table(
            Column("Title", style="green", width=60),
            Column("Release Type", style="green", width=20),
            Column(header="Release Date", style="green", width=20),
            box=box.ROUNDED,
            safe_box=True,
            width=100,
            row_styles=["dim", ""],
            title_style="green"
        )

        sorted_albums = sorted(db_artist.albums, key=lambda album: (priority.get(album['release_type'], 99), album['release_date']), reverse=True)

        table.title = db_artist.artist_name
        
        count = 0
        #studio_albums = [album for album in db_artist.albums if album['release_type'] == "studio_album"]
        for album in sorted_albums:
            truncated_album = (album['album_title'][:53] + '..' if len(album['album_title']) > 55 else album['album_title'])
            table.add_row(truncated_album, album['release_type'], album['release_date'])
            count = count + 1
            if count == 5:
                break

        con.print(table)

        artists = {}

        ans = Prompt.ask("[bold green]Is this the record you wish to delete and refresh? [Y/n][/bold green]").lower()
        if ans in ["y", "yes"]:
            db.remove(artist_name)

            artists = fetch_many_artist_mbid(''.join(artist_name))

            for index, artist in artists.items():
                artists[index] = fetch_artist_albums(artist)
                
            #print("[bold green]The following 5 artists were discovered when rescanning[/bold green]")
            for index, artist in artists.items():
                table = Table(
                    Column("Title", style="green", width=60),
                    Column("Release Type", style="green", width=20),
                    Column(header="Release Date", style="green", width=20),
                    box=box.ROUNDED,
                    safe_box=True,
                    width=100,
                    row_styles=["dim", ""],
                    title_style="green"
                )

                table.title = f"[{index + 1}] {artist.artist_name}"

                count = 0
                sorted_albums = sorted(artists[index].albums, key=lambda album: (priority.get(album['release_type'], 99), album['release_date']), reverse=True)
                for album in sorted_albums:
                    truncated_album = (album['album_title'][:57] + '..' if len(album['album_title']) > 59 else album['album_title'])
                    table.add_row(truncated_album, album['release_type'], album['release_date'])
                    count = count + 1
                    if count == 5:
                        break

                con.print(table)

            ans = Prompt.ask("[bold green]Please select the number that matches the artist you wish to replace [1, 2, 3, 4, 5][/bold green]")
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

        - rich:     https://rich.readthedocs.io/en/latest/tables.html
            - rich is awesome omg

        - sorting list based on priority:   https://www.geeksforgeeks.org/python/python-sort-list-according-to-other-list-order/
                                            https://stackoverflow.com/questions/4233476/sort-a-list-by-multiple-attributes

        - iso 8601 vs iso 8601:             https://www.influxdata.com/blog/python-date-comparison-comprehensive-tutorial/
"""