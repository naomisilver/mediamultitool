from .cleaner.cleaner import run_cleaner
from .playlist.import_csv import convert_csv

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

        blocklist_strs = cfg.playlist.blocklist_strings.split(",")
        allowlist_strs = cfg.playlist.allowlist_strings.split(",")
        container_root = Path(cfg.playlist.container_root)
        local_music_path = Path(cfg.playlist.local_music_path)

        if args.o_directory is not None: # stopped defaulting to the input file location as an output because there wouldn't be one for a url, cleans up run slightly too
            output_file_path = args.o_directory
        else:
            output_file_path = Path(cfg.playlist.default_output)

        if args.recursive:
            csv_files = [x for x in Path(args.input_param).iterdir() if x.suffix == ".csv"] # make list of csv files
            for csv_file in csv_files:
                convert_csv(csv_file, local_music_path, container_root, blocklist_strs, allowlist_strs, output_file_path)

        else: 
            csv_file_path = Path(args.input_param) 
            convert_csv(csv_file_path, local_music_path, container_root, blocklist_strs, allowlist_strs, output_file_path) # toying with the idea of creating a "PlaylistConfig" dataclass
            # to host all these values 

    if args.command == "cleaner":
        dl_path = Path(cfg.cleaner.download_path)
        run_cleaner(dl_path)

    logger.info("Completed in: %s seconds", round(time.time() - start_time, 3))

"""
    Sources/credit:
        - Time keeping: https://stackoverflow.com/questions/1557571/how-do-i-get-time-of-a-python-programs-execution (not necessary, just thought it'd be cool) 
"""