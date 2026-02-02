from pathlib import Path

import os
import shutil
import logging
import pathlib

"""
    TODO:
        clean_downloads(dl_path)
            - iterate through music_path checking if that folder contains any .flac files. if that directory ALSO contains a directory check another layer deep, see if that directory
              contains any flacs and so on. saving only that folder to the empty_dirs list then iterate through the empty dirs list and remove those directories after receiving some
              user input
        move_album(dl_path)
"""

logger = logging.getLogger(__name__)
AUDIO_EXTS = {".flac", ".mp3", ".m4a", ".wav", ".ogg", ".aac", ".alac", ".aiff"}

def clean_downloads(dl_path):
    empty_dirs = []

    for dir in dl_path.iterdir():
        if "[" in dir.name: # from experience, navidrome doesn't recognise artist dirs with any additional info like "[CD]" and album downloads often include the sample rate like "[24B-48kHz]"

            if not any(File.suffix.lower() in AUDIO_EXTS for File in dir.iterdir()):

                discs = [y for y in dir.iterdir() if y.is_dir()] # not happened yet but solves when a download fails for a multi disc album (doesn't trigger for artist dirs because of if "[")

                if not discs:
                    logger.debug("Found empty dir: %s", dir)
                    empty_dirs.append(dir)
                    continue

                for disc in discs:
                    if not any(File.suffix.lower() in AUDIO_EXTS for File in disc.iterdir()):
                        logger.debug("Found empty dir: %s", disc) # same as the first gen expr but for child dirs
                        empty_dirs.append(disc)

    if empty_dirs:
        i = input(f"Found {len(empty_dirs)} empty dirs, delete? (Y/n): ").lower()
        if i in ("y", "yes"):
            for empty_dir in empty_dirs:
                os.rmdir(empty_dir)
        else:
            logger.warning("aborted")
    else:
        logger.info("No empty directories found, continuing")

def combine_artist(dl_path):
    moved_dirs = 0
    dir_list = os.listdir(dl_path)
    logger.info("found %s albums", len(dir_list))

    
    for i in range (len(dir_list)):
        parts = dir_list[i].split("-", 1)

        if len(parts) < 2:
                continue

        artist = parts[0].strip().rstrip(".")
        album = parts[1].strip().rstrip(".")

        if "," in artist:
            artist = artist.split(",")[0].strip()

        a_dir_name = artist
        a_dir_path = os.path.join(dl_path, a_dir_name)

        if not os.path.isdir(a_dir_path):
            os.mkdir(a_dir_path)
            logger.info("Created artist folder: %s", str(a_dir_path))

        try:
            if artist in a_dir_path:
                shutil.move(os.path.join(dl_path, dir_list[i]), a_dir_path)
                moved_dirs += 1

        except FileNotFoundError as e:
            logger.error("%s", e)
    


    logger.info("Moved %s albums into artist folders", moved_dirs)

def run_cleaner(dl_path):

    clean_downloads(dl_path)
    combine_artist(dl_path)

"""
    Sources/credit:
        - generator expressions:                    https://stackoverflow.com/questions/33400682/check-if-a-directory-contains-a-file-with-a-given-extension

        - the diff between gen exp and list comp:   https://www.reddit.com/r/learnpython/comments/mo79oq/are_list_comprehensions_just_generator/
            - before changing to generator expressions, I used list comp to list all files with an extension in AUDIO_EXTS and I did that twice. Then would just check
              if the list was empty with "if not list" so each iterations it would contain an entire list in memory just to check if the dir contained ANY audio files
              the above thread helped understand the difference

        
"""