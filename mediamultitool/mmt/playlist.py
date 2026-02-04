from pathlib import Path

import csv
import os
import logging
import time

logger = logging.getLogger(__name__)

AUDIO_EXTS = {".flac", ".mp3", ".m4a", ".wav", ".ogg", ".aac", ".alac", ".aiff"}
UNIQUE_CHARS = {"&", "-"} # relic of the past, the issue with standardising the normalisation of data is that the usage is almost never consistant. Sometimes the dash is
# in the artist name and need to be removed like in "JAY-Z", sometimes it's in the track name for "... - Remastered 2018" so yes, I could place each normalisation step in their
# own repsective helper function but I would be moving a small mess into several helpers filled with a dozen different conditionals based on where the dash is, and that's just for
# a dash, I still need to explore more standard normalisaion further but the current solution of "do it when needed" is the least messiest.

# just to further this, applying the normalisation on the csv data is easy because I extract the data by name then reconstruct it to the format I need, I can't do that for local path
# names, and especially not dynamically. I wouldn't be able to store say the artist name, album name and track name as seperate values then reconstruct it to match locally as I don't 
# *KNOW* someones local storage is setup the same as mine, theirs might be a different format that navidrome can still detect

"""
TODO:
    - add a bunch of try catch statements and make some tests to handle edge cases
        - what if a bad local_storage path is provided etc...
"""

def read_csv(file_path):
    """ read and return the csv data """

    with open(Path(file_path), encoding="utf-8-sig", newline="") as f: # needs to be encoded in utf-8 at least because that's the "8" in m3u8
        reader_obj = list(csv.DictReader(f)) # import csv data as a dictionary then convert to list, exlcuding the column names

        logger.info("Extracted %s rows of data from '%s'", len(reader_obj), file_path.name)

        return reader_obj

def create_text(file_path, csv_data, container_path):
    """ create a text file from the extracted csv data

    """
    with open(file_path, "a", encoding="utf-8", newline="") as f:
        for row in csv_data: # for each row in the csv dict
            
            artist_name = normalise(row.get("Artist name")); album_name = normalise(row.get("Album")); track_name = normalise(row.get("Track name"))
            
            if "&" in artist_name: # solves the case "&" in "macklemore & ryan lewis"
                artist_name = artist_name.split("&", 1)[0].strip() 

            track_data = artist_name + "/" + album_name + "/" + track_name

            f.write(f"{track_data}\n") # write in the track data and new line that shit

def search_music(file_path, music_path, container_path, blocklist_strs, allowlist_strs):
    """ iterate temp.txt and search for the tracks in local storage """

    missing_tracks = 0
    final_path_list = []
    network_path = str(music_path)

    with open(file_path, "r", encoding="utf-8", newline="") as f:
        for row in f:
            split_path = row.split("/")
            album_found = False
            allowlist = False
            search_roots = []

            album_path = None; artist_path = None; track_path = None
            csv_artist = normalise(split_path[0]); csv_album = normalise(split_path[1]); csv_track = normalise(split_path[2])
            
            csv_album = csv_album.split("(")[0].strip() # solves the case: "Spawn The Album (Soundtrack)"

            csv_track = csv_track.split(" - ", 1)[0] # solves the case: "Smoke On The Water - Remastered 2012"
            
            for s in allowlist_strs:
                if s.lower() in csv_track.lower():
                    allowlist = True
                    allowlist_string = s

            csv_track = csv_track.split("(")[0].strip() # solves thte case: "I Love It (feat. Charli XCX)"
            
            if allowlist:
                csv_track = csv_track + f" {allowlist_string}"

            # artist matching
            for artist in music_path.iterdir():
                folder_artist = normalise(artist.name)

                if "-" in folder_artist: # the ceelo green rule
                    folder_artist = folder_artist.replace("-", "")
                    csv_artist = csv_artist.replace("-", "")

                if folder_artist == csv_artist:
                    artist_path = artist
                    break

            if artist_path == None:
                missing_tracks += 1
                logger.warning("Artist not found for: %s/%s/%s", split_path[0], split_path[1], split_path[2].strip())
                continue
                
            # album matching
            for album in artist_path.iterdir():
                if not album.is_dir(): 
                    continue
                    
                folder_album = album.name
                folder_album = folder_album.split(" - ", 1)[-1] # give me the last part if it exists (because locally (for me) albums are "[Artist] - [Album name]")
                folder_album = folder_album.split("(")[0].strip() # take the first part (before the year, or remaster etc...), strip it and use that

                if normalise(folder_album) == normalise(csv_album):
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
                    if s in track_name: # fixes case taylor swift "(commentary)"
                        blocklist = True
                
                if allowlist:
                    pass
                else:
                    track_name = track_name.split("(")[0].strip()

                # partial matching now because of the above split being moved into an else statement, if "03. LE SSERAFIM - SPAGHETTI (Member ver.) (Remastered).flac" exists locally
                # but csv shows: "SPAGHETTI (Member ver.)", it wouldn't match with exact string matching. Might need to bite the bullet and use regex *shudder*
                if normalise(csv_track) in normalise(track_name) and not blocklist:
                    track_path = track.resolve() # get the absolute path
                    logger.info("Found track: %s ", track.name)
                    final_path_list.append(track_path) 
                    
                    break

            else:
                missing_tracks += 1
                logger.warning("Track not found for: %s/%s/%s", split_path[0], split_path[1], split_path[2].strip())
    
    if missing_tracks != 0:
        logger.warning("Number of missing tracks/albums: %s/%s", missing_tracks, missing_tracks + len(final_path_list))
    logger.info("Created a playlist with %s tracks", len(final_path_list))

    return final_path_list

def normalise(s):
    """ small helper to strip down to the absolute bare required data for string/partial string matching """

    s = s.lower().strip()
    illegal = '<>:"/\\|?*\''
    s = "".join(c for c in s if c not in illegal) # solves the general case of illegal os characters (breaks AC/DC but is solved by discrete artist search)
    s = s.rstrip(".") # solves the case of hkmori's "i just want to be your friend..."
    return s

def recreate_text(file_path, path_data, music_path, container_path):
    """ rewrite the text file with newly added absolute/network path of the music files, prepending the container root as apposed to network path
     
        converts to work for navidrome but could expand into different formats, unsure if jellyfin supports m3u8 but expansion should be easy now 
    """

    with open(file_path, "w",encoding="utf-8", newline="") as f:
        for full_path in path_data:
            relative_path = full_path.relative_to(music_path) # retain only the path after the local storage path

            final_path = container_path / relative_path # prepend the container path to the path

            final_path = str(final_path).replace("\\", "/")

            f.write(final_path + "\n")

def convert_m3u8(file_path, csv_data):
    """ convert temp.txt file to m3u8 """

    p = Path(file_path) # ensure file_path is a Path object (100% unnecessary in deployment but useful for when isolating this function for testing)
    try:
        playlist_name = csv_data[0]['Playlist name'] # extract the playlist name from the csv data
    except IndexError:
        logger.error("Provided CSV file contains no tracks")
        
    m3u8_file = p.parent / f"{normalise(playlist_name)}.m3u8" # get the path and normalise the name (one of my personal playlists is just '?' which is an illegal char in windows)
    
    if m3u8_file.exists(): 
        logger.info("m3u8 file of name: '%s.m3u8' already exists at '%s', overwriting", csv_data[0]['Playlist name'], p.parent)
    
    logger.info("created/modified m3u8 file of name %s at %s", m3u8_file.stem, m3u8_file.parent)
    p.replace(m3u8_file)

def run_playlist(text_file_path, csv_file_path, container_path, local_music_path, blocklist_strs, allowlist_strs):
    """ control function """

    csv_data = read_csv(csv_file_path)
    create_text(text_file_path, csv_data, container_path)
    path_data = search_music(text_file_path, local_music_path, container_path, blocklist_strs, allowlist_strs)
    recreate_text(text_file_path, path_data, local_music_path, container_path)
    convert_m3u8(text_file_path, csv_data)