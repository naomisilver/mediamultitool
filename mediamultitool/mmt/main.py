from .playlist import run_playlist
from .cleaner import run_cleaner

from pathlib import Path 
import logging
import time

logger = logging.getLogger(__name__)

"""
TODO:
"""

def run(args, cfg):
    output_provided = False
    start_time = time.time()

    if args.command == "playlist":
        if args.o_directory is not None:
            output_provided = True

        blacklist_strs = cfg.playlist.blacklist_strings.split(",")
        whitelist_strs = cfg.playlist.whitelist_strings.split(",")
        container_root = Path(cfg.playlist.container_root)
        local_music_path = Path(cfg.playlist.local_music_path)

        if args.recursive:
            if output_provided:
                text_file_path = args.o_directory / "temp.txt"
            else:
                text_file_path = args.i_directory / "temp.txt"

            csv_files = [x for x in args.i_directory.iterdir() if x.suffix == ".csv"]
            for csv_file in csv_files:
                run_playlist(text_file_path, csv_file, container_root, local_music_path, blacklist_strs, whitelist_strs)

        else:
            if output_provided:
                text_file_path = args.o_directory / "temp.txt" # output will always be a dir not a file and is checked in cli so can work with known good data
            else:
                text_file_path = args.i_directory.parent / "temp.txt" # if output not provided, take the parent of the input file and use that
            
            csv_file_path = args.i_directory 
            run_playlist(text_file_path, csv_file_path, container_root, local_music_path, blacklist_strs, whitelist_strs)

    if args.command == "cleaner":
        dl_path = Path(cfg.cleaner.download_path)
        run_cleaner(dl_path)

    logger.info("Completed in: %s seconds", round(time.time() - start_time, 3))

"""
    Sources/credit:
        - Time keeping: https://stackoverflow.com/questions/1557571/how-do-i-get-time-of-a-python-programs-execution (not necessary, just thought it'd be cool) 
"""