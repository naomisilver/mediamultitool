from ..models import Track, PlaylistConfig

from .create_m3u8 import create_m3u8
from .normalise import normalise

from pathlib import Path

import os
import logging

logger = logging.getLogger(__name__)

AUDIO_EXTS = {".flac", ".mp3", ".m4a", ".wav", ".ogg", ".aac", ".alac", ".aiff"}

"""
TODO
    - Currently, "30 Seconds To Mars" is stored in spotify as "Thirty Seconds To Mars", meaning none of this current logic can account for that. The plan is
      to setup an "aliases" set that I can give known bad data, like the afformentioned, and assign it new aliases and I can be somewhat cheeky with and do:
      artist_alises = {
            "30 seconds to mars": {"thirty seconds to mars"}
            "thirty seconds to mars": {"30 seconds to mars"}
      }
      this means I don't break compatibility if a music provider changes it's alias for them or it's different locally for another user, however, I am yet
      again feature creeping myself when I need to do small updates :P, will come soon and will document in issues

      even better, I can put this in the config with a bunch of defaults as examples (also means I don't need to account for absolutely everything
      like how I handle blocklist/allowlist strings)
"""

def get_container_path(track_paths, music_path, pl_cfg):
    """ removes the absolute path portion from the audio file path and prepends the container root provided in config.toml """
    container_paths = []

    for track in track_paths:
        relative_path = track.relative_to(music_path)

        final_path = track / relative_path

        final_path = str(final_path).replace("\\", "/")

        container_paths.append(final_path)

    return container_paths


def search_music(tracks, pl_cfg: object, playlist_name):
    """ iterate tracks and search for the tracks in local storage """
    allowlist_strs = pl_cfg.allowlist_strs
    blocklist_strs = pl_cfg.blocklist_strs
    music_path = pl_cfg.local_music_path

    missing_tracks = 0
    full_path_list = []
    network_path = str(pl_cfg.local_music_path)

    for t in tracks:
        search_roots = []
        allowlist = False
        album_found = False

        album_path = None; artist_path = None; track_path = None
        raw_artist = normalise(t.artist); raw_album = normalise(t.album); raw_track = normalise(t.track)

        if "&" in raw_artist: # solves the case "&" in "macklemore & ryan lewis"
            raw_artist = raw_artist.split("&", 1)[0].strip()
        if "-" in raw_artist:
            raw_artist = raw_artist.replace("-", "") # was previously performing this normalisation in the artist matching section which meant it
            # would not be performed, will look at moving these into a special rule (this time probably not definable by users)

        artist_names = {raw_artist} # convert raw artist to a set

        for key, value in pl_cfg.artist_aliases.items(): # solves the case: "30 Seconds to mars" locally, "Thirty Seconds To Mars" in playlist data
            n_key = normalise(key)
            n_value = normalise(value)

            if raw_artist in {n_key, n_value}: # iterate through the the dictionary
                artist_names.update({n_key, n_value}) # and normalise the provided values and add that to the artist_names set

        raw_album = raw_album.split("(")[0].strip() # solves the case: "Spawn The Album (Soundtrack)"

        raw_track = raw_track.split(" - ", 1)[0] # solves the case: "Smoke On The Water - Remastered 2012"

        for s in allowlist_strs:
            if s.lower() in raw_track.lower():
                allowlist = True
                allowlist_string = s

        raw_track = raw_track.split("(")[0].strip() # solves thte case: "I Love It (feat. Charli XCX)"

        if allowlist:
            raw_track = raw_track + f" {allowlist_string}"

        # artist matching
        for artist in music_path.iterdir():
            folder_artist = normalise(artist.name)

            if "-" in folder_artist: # the ceelo green rule
                folder_artist = folder_artist.replace("-", "")

            for artist_name in artist_names:
                if folder_artist == artist_name:
                    artist_path = artist
                    break
        
        if artist_path == None:
            missing_tracks += 1
            logger.warning("Artist not found for: %s/%s/%s", t.artist, t.album, t.track.strip())
            continue

        # album matching
        for album in artist_path.iterdir():
            if not album.is_dir():
                continue

            folder_album = album.name
            folder_album = folder_album.split(" - ", 1)[-1] # give me the last part if it exists (because locally (for me) albums are "[Artist] - [Album name]")
            folder_album = folder_album.split("(")[0].strip() # take the first part (before the year, or remaster etc...), strip it and use that

            if normalise(folder_album) == normalise(raw_album):
                album_path = album
                album_found = True

                break
        
        if album_found: # for cases like: "In the Air Tonight","Phil Collins","Rock",..." where spotify completely misses what album the song ACTUALLY comes from.
            search_roots.append(album_path) # narrow search when it can and wide search only when needed
        else:
            search_roots.append(artist_path)

        # track matching
        for track in search_roots[0].rglob("*"): # recursive search through all sub directories (to avoid disc 1, disc 2) as the only thing to search for is tracks
            if track.suffix.lower() not in AUDIO_EXTS: # stops something like cover.jpg being considered as a track
                continue

            blocklist = False

            track_name = track.stem
            track_name = track_name.split(" - ", 1)[-1] # slightly messy but strips away without regex, takes away the "[Artist] -" from local files and keep the second part if there
            track_name = track_name.split(" - ", 1)[0]  # performs it again if there's say "- remaster 2011" and then keeps the first

            for s in blocklist_strs:
                if s in track_name: # solves case taylor swift "(commentary)"
                    blocklist = True

            if allowlist:
                pass
            else:
                track_name = track_name.split("(")[0].strip()

            # partial matching now because of the above split being moved into an else statement, if "03. LE SSERAFIM - SPAGHETTI (Member ver.) (Remastered).flac" exists locally
            # but raw shows: "SPAGHETTI (Member ver.)", it wouldn't match with exact string matching. Might need to bite the bullet and use regex *shudder*
            if normalise(raw_track) in normalise(track_name) and not blocklist:
                track_path = track.resolve()
                logger.info("Found track: %s ", track.name)
                full_path_list.append(track_path)

                break
            
        else:
            missing_tracks += 1
            logger.warning("Track not found for: %s/%s/%s", t.artist, t.album, t.track.strip())

    if missing_tracks > 0: 
        logger.warning("Number of missing tracks or albums: %s/%s", missing_tracks, missing_tracks + len(full_path_list))
    
    logger.info("Successfully matched %s tracks", len(full_path_list))

    container_paths = get_container_path(full_path_list, music_path, pl_cfg)

    create_m3u8(container_paths, pl_cfg, playlist_name)

"""
    Sources/credit:
        - artist_aliases dict:  https://www.w3schools.com/python/python_dictionaries_add.asp
                                https://stackoverflow.com/questions/38987/how-do-i-merge-two-dictionaries-in-a-single-expression-in-python
                                https://stackoverflow.com/questions/483666/reverse-invert-a-dictionary-mapping
            - i didn't uses the bottom two as that was the inital approach and didn't yet know the power of sets
"""