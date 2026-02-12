from .normalise import normalise

from pathlib import Path

import os
import logging

logger = logging.getLogger(__name__)


def create_m3u8(tracks, pl_cfg: object, playlist_name):
    """ create an m3u8 file containing relative paths returned from search.py """
    p = Path(pl_cfg.output_path)
    
    m3u8_file = pl_cfg.output_path / f"{normalise(playlist_name)}.m3u8"

    if m3u8_file.exists():
        logger.info("m3u8 file of name: '%s.m3u8' already exists at '%s', overwriting", playlist_name, p)
        with open(m3u8_file, "w", encoding="utf-8", newline="") as f:
            for track in tracks:
                f.write(track + "\n")
    else:
        with open(m3u8_file, "a", encoding="utf-8", newline="") as f:
            for track in tracks:
                f.write(track + "\n")

    logger.info("created/modified m3u8 file of name %s at %s \n" \
    "~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-", m3u8_file.stem, m3u8_file.parent)
    # idrk if this is the best way to split up logging content but when testing with multiple inputs it's somewhat difficult
    # to immediately know where one playlist ends and another starts
