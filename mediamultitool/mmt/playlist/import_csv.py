from ..models import Track # track class

from .search import search_music

from pathlib import Path

import logging
import csv

logger = logging.getLogger(__name__)

def parse_csv(file_path):
    """ read and return the csv data """

    with open(Path(file_path), encoding="utf-8-sig", newline="") as f: # needs to be encoded in utf-8 at least because that's the "8" in m3u8
        reader_obj = list(csv.DictReader(f)) # import csv data as a dictionary then convert to list, exlcuding the column names

        logger.info("Extracted %s rows of data from '%s'", len(reader_obj), file_path.name)

        return reader_obj
    
def convert_csv(csv_file_path, pl_cfg: object):
    """ take the outputted reader_obj and assign it's dictionary values to Track object values """
    track_list = []

    csv_data = parse_csv(csv_file_path)

    playlist_name = csv_data[0]["Playlist name"]

    for row in csv_data:
        artist_name = row.get("Artist name")
        album_name = row.get("Album") # mostly copied from the old playlist.py "recreate_txt" function but substituting for the new Track class/objects
        track_name = row.get("Track name")

        track_list.append(Track( 
                artist = artist_name,
                album = album_name,
                track = track_name
            )
        )

    search_music(track_list, pl_cfg, playlist_name)
    