from dataclasses import dataclass

@dataclass
class Track:
    artist: str
    album: str | None # nullable in case I can't find lastfm album name from api request
    track: str

"""
    Sources/credit:
        - I haven't used dataclasses in this way before and so wanted to know best practice for where to put it, turns out no one knows! (from what I could find)
          the closest I could get was that "models.py" is used in django development
"""