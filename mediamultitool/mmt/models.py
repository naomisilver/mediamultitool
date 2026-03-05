from dataclasses import dataclass, field
from pathlib import Path

@dataclass(slots=True) # supposedly slotted dataclasses are better than standard (__dict__?) https://news.ycombinator.com/item?id=41804093, like always, you can never get a straight answer :D
class Track:
    artist: str
    album: str | None # nullable in case I can't find lastfm album name from api request
    track: str

@dataclass(slots=True)
class LocalArtist: # represents what was found locally
    artist_name: str
    latest_album: str
    all_albums: list[str] = field(default_factory=list)

@dataclass(slots=True)
class CachedArtist: # represents what I got back from musicbrainz/what exists in the db cache
    artist_mbid: str
    artist_locale: str 
    artist_name: str
    ended: int = 0
    last_checked: int = 0 # using unix timestamp, take the current timestamp, subtract what is stored in db, if longer than 604,800 (a week) then update local cache
    studio_albums: list[str] = field(default_factory=list)
    singles: list[str] = field(default_factory=list)
    eps: list[str] = field(default_factory=list)
    live_albums: list[str] = field(default_factory=list)
    compilations: list[str] = field(default_factory=list)

@dataclass(slots=True)
class PlaylistConfig:
    local_music_path: Path
    container_root: Path
    output_path: Path
    lastfm_api_key: str | None # nullable because a user may not want to convert last.fm playlists
    blocklist_strs: list[str] = field(default_factory=list) # default to an empty list
    allowlist_strs: list[str] = field(default_factory=list)
    artist_aliases: dict[str, str] = field(default_factory=dict)

@dataclass(slots=True)
class UpdaterConfig: # small now but will make things easier if I do move to automatic downloading via streamrip
    local_music_path: Path
    all_or_new: bool
    ignore: dict[str, bool] = field(default_factory=dict) # store the ignores in a dictionary so I can iterate over it, no more big if block

"""
    Sources/credit:
        - I haven't used dataclasses in this way before and so wanted to know best practice for where to put it, turns out no one knows! (from what I could find)
          the closest I could get was that "models.py" is used in django development
        - empty list defaults for dataclass attributes: https://dev.to/devasservice/python-trick-using-dataclasses-with-fielddefaultfactory-4159
"""