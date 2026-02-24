from ..models import CachedArtist, LocalArtist

from platformdirs import user_config_dir
from pathlib import Path

import sqlite3
import json
import os
import time
import logging

logger = logging.getLogger(__name__)

one_minute_unix_time = 60
one_hour_unix_time = 3600
one_day_unix_time = 86400 # somewhat temporary while testing
one_week_unix_time = 604800

APP_NAME = "mediamultitool"
APP_DIR = Path(user_config_dir(APP_NAME))
LOG_DIR = APP_DIR / "logs" # copy pasted from cli.py with the added DB_PATH, will be moving to paths.py in a later issue/commit
LOG_PATH = APP_DIR / "logs" / "mmt.log"
DB_PATH = APP_DIR / "updater.db"

"""
    TODO:
        - I really need to find a way to condense these methods, I'm repeating the same steps and espc for db.add(), docstrings as part of a callable should be illegal

        - it's also currently not very polymorphic of me right me, but I want to get the rest of it working before  
"""

class Database:
    def __init__(self):
        self.db_path = DB_PATH # will be moving to a "paths.py" script to be able to import each respective path
        # for now, this is the way it is

        if not os.path.exists(self.db_path): # means it will always make itself on first run of updater
            self.create_db()

    def create_db(self):
        """ create the database and table """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""CREATE TABLE artists (
                  artist_mbid text PRIMARY KEY,
                  artist_name text NOT NULL UNIQUE,
                  artist_locale text NOT NULL,
                  ended integer NOT NULL,
                  last_checked integer NOT NULL,
                  studio_albums text,
                  eps text,
                  singles text,
                  compilations text,
                  live_albums text
                  )""")
        
        # mbid will be the primary key because it is wholey unique, annoyingly, I can't using it to search the db initially because that is the first thing I need from musicbrainz, I *could*
        # use lastfm to pull the mbid but then if there's a mismatch for whatever reason, it'll be annoying to find why I'm getting incorrect data
        # so instead, we use the artist_name as the index, what I'll be using to compare what there is locally to the DB, if that artist's name is in the db, we can assume we already have
        # their mbid, meaning I can skip checking for it
        
        logger.debug("Created DB at %s", self.db_path)
        
        conn.commit()
        conn.close()

    def is_exists(self, artist_name) -> CachedArtist | None: # returns either the artist name if it exists or None if it doesn't
        """ retrieves a given artist row if it exists """

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("SELECT * FROM artists WHERE artist_name = ?", (artist_name,)) # need to encompass a variable with parenthesis to make it look like a tuple (for some reason,
        # found it here https://www.sqlitetutorial.net/sqlite-python/sqlite-python-select/)

        row = c.fetchone()

        logger.debug("Searched DB for: %s")

        conn.close()

        if row is None:
            return None
        
        return CachedArtist(
            artist_mbid = row[0],
            artist_name = row[1],
            artist_locale = row[2],
            ended = row[3],
            last_checked = row[4],
            studio_albums = json.loads(row[5]),
            eps =  json.loads(row[6]),
            singles = json.loads(row[7]),
            compilations = json.loads(row[8]),
            live_albums = json.loads(row[9])
        )
        
    def is_stale(self) -> list[CachedArtist]:
        """ checks for 'stale' artists to refresh cache """

        outdated = []

        t = int(time.time())

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("SELECT * FROM artists WHERE (? - last_checked) > ?", (t, one_minute_unix_time))

        rows = c.fetchall()

        conn.close()

        if rows is None:
            return None

        for row in rows:
            outdated.append(CachedArtist(
                artist_mbid = row[0],
                artist_name = row[1],
                artist_locale = row[2],
                ended = row[3],
                last_checked = row[4],
                studio_albums = json.loads(row[5]),
                eps =  json.loads(row[6]),
                singles = json.loads(row[7]),
                compilations = json.loads(row[8]),
                live_albums = json.loads(row[9])
            ))

        return outdated

    def add(self, artist: CachedArtist):
        """ adds new artist into db """

        t = int(time.time())

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("""
                INSERT INTO artists (
                    artist_mbid,
                    artist_name,
                    artist_locale,
                    ended,
                    last_checked,
                    studio_albums,
                    eps,
                    singles,
                    compilations,
                    live_albums
                  )
                  VALUES (?,?,?,?,?,?,?,?,?,?)
                  ON CONFLICT (artist_mbid)
                  DO Update SET
                    artist_name = excluded.artist_name,
                    artist_locale = excluded.artist_locale,
                    ended = excluded.ended,
                    last_checked = excluded.last_checked,
                    studio_albums = excluded.studio_albums,
                    eps = excluded.eps,
                    singles = excluded.singles,
                    compilations = excluded.compilations,
                    live_albums = excluded.live_albums
                 """,
                    (
                    artist.artist_mbid,
                    artist.artist_name,
                    artist.artist_locale,
                    int(artist.ended),
                    t,
                    json.dumps(artist.studio_albums),
                    json.dumps(artist.eps),
                    json.dumps(artist.singles),
                    json.dumps(artist.compilations),
                    json.dumps(artist.live_albums),
                    ))
        
        conn.commit()

        conn.close()

"""
    Sources/credit:
        - Classes:                  https://www.w3schools.com/python/python_class_init.asp
            - needed a refresher
        
        -  SQLite3                  https://sqlitebrowser.org/dl/
                                    https://www.youtube.com/watch?v=byHcYRpMgI4&t=1s
                                    https://www.w3schools.com/sql/sql_primarykey.ASP
                                    https://docs.python.org/3/library/sqlite3.html
                                    https://www.sqlitetutorial.net/sqlite-python/sqlite-python-select/

        - String to list and back   https://www.reddit.com/r/learnpython/comments/1bc25ef/comment/kudft6b/?utm_source=share&utm_medium=web3x&utm_name=web3xcss&utm_term=1&utm_content=share_button
                                    https://www.geeksforgeeks.org/python/json-loads-in-python/
                                    which led me down to json.dumps()
                                    https://www.geeksforgeeks.org/python/json-dumps-in-python/

        - unix timestamping:        https://www.geeksforgeeks.org/python/how-to-convert-datetime-to-unix-timestamp-in-python/
        - better unix time:         https://stackoverflow.com/questions/16755394/what-is-the-easiest-way-to-get-current-gmt-time-in-unix-timestamp-format
   
"""