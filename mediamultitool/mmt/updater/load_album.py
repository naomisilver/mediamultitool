from ..models import Artist, UpdaterConfig
from .get_albums import process_artist_albums

from pathlib import Path
import logging
import re

logger = logging.getLogger(__name__)

"""
TODO:
    - I fixed the multiple potential tag issue by using the latest tag found as the source of truth, though that may not hold up and may need to add further checks.
      However, when a year tag isn't present, I *think* I want to try and automatically update them. Though that will come later.

02/16/26 09:38:24 | ERROR: TypeError, '>' not supported between instances of 'NoneType' and 'int' attempting to compare None to 2024. Source: The Mark, Tom & Travis Show (The Enema Strikes Back) [Live]
02/16/26 09:38:24 | ERROR: TypeError, '>' not supported between instances of 'NoneType' and 'int' attempting to compare None to 2019. Source: Bring Me The Horizon - Music to listen to~dance to

    - after the above, work on get_album.py (name not decided yet), which recieves the list of Artist objects, iterates through and uses the artist's name
      to query last.fm and get a list of albums from them (i don't know how last.fm handles artists with the same name so this is going to be fun), then compare the 
      newest album returned from last.fm to the latest found locally, if last.fm's is newer step through the list until the latest_album attribute matches the one
      in the last.fm list. if (somehow) the locally is newer, then probably log that then move on. Save all the "to download" albums to a list (for use later) and
      print it.

    - there's some things to consider like:
        - allowing the user to search for only the given artists through the cli, e.g., "mmt updater -only blink-182 YOASOBI"
        - allowing the user to search ignoring the given artists through the cli, e.g., "mmt updater -exlcuding blink-182 YOASOBI"
        - then in config:
            - allowing the user to define a list of "always ignore" list so they don't need to repeatedly add the same artists as args

    - downloading is going to be a beast on its own, my absolute best bet would be to look at using streamrip though their "scripting with streamrip" wiki page
      is woefully lacking, it allows searching using a metadata tag but not sure what that metadata represents, last.fm albumID? qobuz? idk but I could really do
      with using their search functionality to find it, otherwise I'm kinda boned
"""

def regex_tag_check(s):
    """ helper to find the release year of a given album """

    tags = re.findall("\([0-9][0-9][0-9][0-9]\)", s)

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

def normalise_album(s): # was going to use regex but not really necessary when albums (thankfully) follow a very similar naming scheme
    # and I can throw out the multiple artists as I would imagine, last.fm will return the correct album if I search using any of the artists + album name
    """ helper to generalise a given album e.g., "(1999), (Live)" etc """

    s = s.split(" - ", 1)[-1].split("(", 1)[0].strip()

    return s

def get_newest_album(upd_cfg: UpdaterConfig):
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

        artist_data.append(Artist(
            artist_name = artist_name,
            latest_album = normalise_album(newest_album), # before adding to the Artist object, I could really do with normalising/generalising it similar to playlist, though I really don't feel like
            # mirroring the same logic so will look at how I could handle it using regex. 
            all_albums = [normalise_album(album) for album in all_albums] # god I love list comprehension
        ))

    process_artist_albums(upd_cfg, artist_data)

"""
    Sources/credit:
        - regex:    https://www.w3schools.com/python/python_regex.asp
                    https://www.geeksforgeeks.org/python/check-for-balanced-parentheses-in-python/

                    - I'm finally biting the bullet and I have a feeling this regex sources section is going to get pretty large... 
"""