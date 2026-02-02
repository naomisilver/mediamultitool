from .main import run
from ..config import load_config

from logging.handlers import RotatingFileHandler
from argparse import ArgumentParser
from platformdirs import user_config_dir
from pathlib import Path

import argparse
import os
import logging
import sys
import webbrowser

"""
TODO:   
    - feature idea: a way to keep up to date on what music people are releasing
        - iterdir through the entire local music folder, list out the artists and their albums, storing them in a a list of tuples where I can do artist[i].album[x] then query an
          open/free music db to check their newest album. (I could use the year on the album: SAWTOWNE - Brainstorm (JP Ver.) (2025) [FLAC] [16B-44100kHz]) I would need to grab only the year
          which likely means regex :vomit face:, then assign that album to "latest_album", check if there are any newer ones, then log those newer albums. Rate limiting will be an issue
          so I need to ensure I'm only querering once per artist at the absolute worst. (if the music db stores dead artists or something, I could place those in a db file to save queries)

    - look at improving console logging by using rich
"""

class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;239m"
    green = "\x1b[38;5;48m"
    yellow = "\x1b[33;5;222m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = "%(asctime)s | %(levelname)s: %(message)s"

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: green + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }
    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%m/%d/%y %H:%M:%S")
        return formatter.format(record)

def validate_input(parser, args, cfg, APP_DIR):
    try:
        if args.command == "playlist":
            if args.i_directory is None: # if directory is not provided
                parser.error("-p/-playlist requires a path to operate on")

            if os.path.isfile(args.i_directory):
                if args.recursive: # if directory given is a file AND recursive is selected
                    parser.error("Cannot recursively generate a playlist from a single file")
                pass

            if os.path.isdir(args.i_directory):
                for file in args.i_directory.iterdir():
                    if file.suffix.lower() == ".csv":
                        continue
                    else:
                        parser.error("Input directory requires csv file to operate on")
                if not args.recursive: # if directory given is the parent folder and recursive isn't selected
                    parser.error("Directories require the -r/-recursive flag")
                pass

            if args.o_directory is not None:
                if os.path.isfile(args.o_directory):
                    parser.error("Output directory cannot be a file")
        
        if cfg.playlist.local_storage_path == "": # if a known required value isn't given, will rely on something else to get user to fill out config when other features are added
            parser.error("Required fields in config are not filled out... (Run 'mmt -c' to open config)")

    except AttributeError:
        pass

def mmt():
    APP_NAME = "mediamultitool"
    APP_DIR = Path(user_config_dir(APP_NAME))
    LOG_DIR = APP_DIR / "logs"
    LOG_PATH = APP_DIR / "logs" / "mmt.log"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    REPO_LINK = "https://github.com/naomisilver/mediamultitool"

    global logger

    file_handler = RotatingFileHandler(
        LOG_PATH, 
        maxBytes=500_000,
        backupCount=1,
        encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s: %(message)s", datefmt="%m/%d/%y %H:%M:%S"))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(CustomFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logger = logging.getLogger(__name__)

    cfg = load_config()

    parser = argparse.ArgumentParser(prog="mmt", description="a multi-function cli tool to manage self hosted media")

    # global options
    parser.add_argument("-c", "--config", action="store_true", help="open show config path and exit")
    parser.add_argument("-l", "--logs", action="store_true", help="open logs path and exit")
    parser.add_argument("-gh", "--github", action="store_true", help="open GitHub Repo and exit")
    parser.add_argument("-v", "--verbose", action="store_true", help="show everything")
    parser.add_argument("-q", "--quiet", action="store_true", help="show nothing")
    
    # all common options (shared across commands)
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("-r", "--recursive", action="store_true", help="perform action recursively")

    subparsers = parser.add_subparsers(dest="command", title="subcommands")

    # playlist subparsing
    playlist_parser = subparsers.add_parser("playlist", aliases=["p"], parents=[common_parser])
    playlist_parser.add_argument("i_directory", nargs="?", type=Path, help="Input directory") # these may not stay part of the sub parser, depends on future features
    playlist_parser.add_argument("o_directory", nargs="?", type=Path, help="Output directory") # at which they will be adjusted
    playlist_parser.set_defaults(command="playlist") 

    # cleaner subparsing
    cleaner_parser = subparsers.add_parser("cleaner", aliases=["c"], parents=[common_parser])
    cleaner_parser.set_defaults(command="cleaner")

    args = parser.parse_args()

    try:
        if args.verbose:
            console_handler.setLevel(logging.DEBUG)
        if args.quiet:
            console_handler.setLevel(logging.ERROR) 
    except AttributeError:
        pass

    if args.config:
        print(f"Opening config file at: {APP_DIR / 'config.toml'}", end='')
        webbrowser.open(f"file:{APP_DIR / 'config.toml'}")
        raise SystemExit
    if args.logs:
        print(f"Opening log file at: {LOG_PATH}") 
        webbrowser.open(LOG_PATH) # **SHOULD** be platform agnostic if not need to look at alternatives (dont have anything apple or none headless Linux system atm)
        raise SystemExit
    if args.github:
        print(f"Opening GitHub at: {REPO_LINK}")
        webbrowser.open(REPO_LINK)
        raise SystemExit

    validate_input(parser, args, cfg, APP_DIR)

    run(args, cfg)

if __name__ == "__main__":
    mmt()

"""
    Sources/credit:
        - Custom logginng colours:  https://stackoverflow.com/questions/384076/how-can-i-color-python-logging-output
                                    https://stackoverflow.com/questions/4842424/list-of-ansi-color-escape-sequences
        
        - Logging to file AND con:  https://betterstack.com/community/questions/how-to-log-to-file-and-console-in-python/

        - Logging module in gen:    https://www.dash0.com/guides/logging-in-python
                                    https://docs.python.org/3/howto/logging.html
"""