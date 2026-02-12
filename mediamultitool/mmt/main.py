from .cleaner.cleaner import run_cleaner
from .playlist.import_csv import convert_csv
from .playlist.import_lastfm import scrape_lastfm_playlist

from .models import PlaylistConfig

from pathlib import Path 
import logging
import time

logger = logging.getLogger(__name__)

"""
TODO:
"""

def run(args, cfg):
    """ main control function """
    input_params = args.input_param 
    output_provided = False
    start_time = time.time()

    if args.command == "playlist":

        if args.output_dir is not None: # stopped defaulting to the input file location as an output because there wouldn't be one for a url, cleans up run slightly too
            output_dir = Path(args.output_dir)
        else:
            output_dir = Path(cfg.playlist.default_output)

        playlist_cfg = PlaylistConfig(
            local_music_path = Path(cfg.playlist.local_music_path),
            container_root = Path(cfg.playlist.container_root),
            output_path = output_dir,
            lastfm_api_key = cfg.apis.lastfm_api_key,
            blocklist_strs = cfg.playlist.blocklist_strings.split(","),
            allowlist_strs = cfg.playlist.allowlist_strings.split(",")
        )

        input_param = [x for x in input_params if x.startswith("http")]
        if input_param:
            for i in input_param:
                split_url = i.split("/", 2)[-1].split("/", 1)[0] # split off "http(s)://" be left with "www.last.fm/...", then split off the final "/"
                if "last.fm" in split_url:
                    scrape_lastfm_playlist(i, playlist_cfg)
                elif "spotify.com" in split_url: # spotify cannot be scraped (at least as far as I can tell, they obfuscate class names so it's not reliable)
                    print() # will need to use the spotify API for that, and iirc what I need will be free
                elif "qobuz.com" in split_url: # qobuz uses both play.qobuz and open.qobuz both with different html so need to account for that, this can 
                    print() # probably be handled using a similar method to last.fm with scraping
        
        else:
            if args.recursive: # will very likely make this defunct in the future, I prefer the idea of multiple inputs
                # over one input with many potential input files. Depends what this all looks like when i add lastfm, spotify etc...
                # scraping/api parsing
                for i in input_params:
                    csv_files = [x for x in Path(i).iterdir() if x.suffix == ".csv"] # make list of csv files
                    for csv_file in csv_files:
                        convert_csv(csv_file, playlist_cfg)

            else:
                for i in input_params: # args.input_param now gives a list so iterate through
                    csv_file_path = Path(input) 
                    convert_csv(csv_file_path, playlist_cfg)

    if args.command == "cleaner":
        dl_path = Path(cfg.cleaner.download_path)
        run_cleaner(dl_path)

    logger.info("Completed in: %s seconds", round(time.time() - start_time, 3))

"""
    Sources/credit:
        - Time keeping: https://stackoverflow.com/questions/1557571/how-do-i-get-time-of-a-python-programs-execution (not necessary, just thought it'd be cool) 
"""