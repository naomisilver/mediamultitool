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

def validate_input(parser, args, cfg, APP_DIR): # there HAS to be a better way handle induvidual param validation ts getting out of control
    try:
        if args.command == "playlist":
            if args.input_param is None: # if directory is not provided
                parser.error("-p/-playlist requires an input to operate on")

            if args.o_directory is not None:
                if os.path.isfile(args.o_directory): # if output dir is a file
                    parser.error("Output directory cannot be a file")

            if args.o_directory is None: # if output dir is empty
                if cfg.playlist.default_output == "": # and default output in config is empty, slap the users hand
                    parser.error("Either an output needs to be given, or default output be defined in config, -c/--config toopen config file")
                elif Path(cfg.playlist.default_output).is_dir():
                    pass
                else:
                    parser.error("default output in the configuration file is not valid, please change, -c/--c to open config file")

            if cfg.playlist.local_storage_path == "": # if a known required value isn't given, will rely on something else to get user to fill out config when other features are added
                parser.error("-p/-playlist operation requires a path to local music files, -c/--config to open config file")
            else:
                if Path(cfg.playlist.local_storage_path).is_dir():
                    pass
                else:
                    parser.error("path to local storage is not quite right, please ensure this is correct")

            if os.path.isfile(Path(args.input_param)):
                if args.recursive: # if directory given is a file AND recursive is selected
                    parser.error("Cannot recursively generate a playlist from a single file")
                pass

            if os.path.isdir(Path(args.input_param)):
                for file in args.i_directory.iterdir():
                    if file.suffix.lower() == ".csv": # TODO replace with gen expr
                        continue
                    else:
                        parser.error("Input directory requires csv file to operate on")
                if not args.recursive: # if directory given is the parent folder and recursive isn't selected
                    parser.error("Directories require the -r/-recursive flag")
                pass

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
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(CustomFormatter())

    pkg_logger = logging.getLogger("mediamultitool")
    pkg_logger.setLevel(logging.INFO) # i nearly ragged my hair out, trying to diagnose an API issue ran it in verbose and got an ungodly amount of shite from selenium
    pkg_logger.addHandler(file_handler) # also turns out this is better practice anyway, see refs
    pkg_logger.addHandler(console_handler)

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
    common_parser.add_argument("-r", "--recursive", action="store_true", help="perform action recursively") # this is going to be depricated in the future

    subparsers = parser.add_subparsers(dest="command", title="subcommands")

    # playlist subparsing
    playlist_parser = subparsers.add_parser("playlist", aliases=["p"], parents=[common_parser])
    playlist_parser.add_argument("input_param", nargs="+", type=str, help="Input Parameter (link to playlist or path to csv file)") # moving away from either single csv or dir of csv in
    playlist_parser.add_argument("-o", "--output", dest="output_dir", type=Path, help="Output directory") # favour of multiple inputs, with an optional output flag
    playlist_parser.set_defaults(command="playlist") 

    # cleaner subparsing
    cleaner_parser = subparsers.add_parser("cleaner", aliases=["c"], parents=[common_parser])
    cleaner_parser.set_defaults(command="cleaner")

    args = parser.parse_args()

    try:
        if args.quiet:
            pkg_logger.setLevel(logging.ERROR) 
        if args.verbose:
            pkg_logger.setLevel(logging.DEBUG)
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

        - pkg_logger:               https://www.reddit.com/r/learnpython/comments/1fcygqa/whats_the_best_way_to_include_a_logger_in_a/
            - stumbled onto the best practice for loggers, never format the root_logger as that is what is imported by other packages
              this way the logger specific to this package when run as an application will have the pretty colours and formatting
              but when imported will not.
            - TL;DR, mediamultitool run as a user is the parent so I control the logging output and handlers and stuff, when imported,
              it is a child and so the parent program should dictate logging output (though I doubt this'll ever get imported to another proj)
"""