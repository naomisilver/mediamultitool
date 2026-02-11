from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class Track:
    artist: str
    album: str | None # nullable in case I can't find lastfm album name from api request
    track: str

@dataclass(slots=True)
class PlaylistConfig:
    local_music_path: Path
    container_root: Path
    output_path: Path
    blocklist_strs: list[str] = field(default_factory=list)
    allowlist_strs: list[str] = field(default_factory=list)

"""
    Sources/credit:
        - I haven't used dataclasses in this way before and so wanted to know best practice for where to put it, turns out no one knows! (from what I could find)
          the closest I could get was that "models.py" is used in django development
        - empty list defaults for dataclass attributes: https://dev.to/devasservice/python-trick-using-dataclasses-with-fielddefaultfactory-4159
"""