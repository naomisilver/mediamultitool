from dataclasses import dataclass, field
from pathlib import Path

@dataclass(slots=True) # supposedly slotted dataclasses are better than standard (__dict__?) https://news.ycombinator.com/item?id=41804093, like always, you can never get a straight answer :D
class Track:
    artist: str
    album: str | None # nullable in case I can't find lastfm album name from api request
    track: str

@dataclass(slots=True)
class Artist:
    artist_name: str
    latest_album: str
    all_albums: list[str] = field(default_factory=list)
    mbid: str | None = None # I can query musicbrainz with a string of the artist name to get the mbid to then use to get accurate album releases :D
    ended: bool = False # MUSICBRAINZ EXPOSES THIS YIPEPEEE


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

"""
    Sources/credit:
        - I haven't used dataclasses in this way before and so wanted to know best practice for where to put it, turns out no one knows! (from what I could find)
          the closest I could get was that "models.py" is used in django development
        - empty list defaults for dataclass attributes: https://dev.to/devasservice/python-trick-using-dataclasses-with-fielddefaultfactory-4159
"""