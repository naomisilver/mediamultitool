from .models import CachedArtist, LocalArtist

from rich import print, box
from rich.console import Console, Group
from rich.table import Table, Column
from rich.prompt import Prompt
from rich.live import Live

class RichUI:
    def __init__(self):
        self.albums = []
        self.live = Live(self.render(), refresh_per_second=2)
        self.live.__enter__()

    def render(self):
        renderables = [self._make_updater_get_albums_table()]

        if self.albums:
            renderables.append(self._make_updater_get_albums_table())

        return Group(*renderables)
    
    def refresh(self):
        self.live.update(self.render())

    def _new_table(self, **overrides):
        config = {
            "box": box.ROUNDED,
            "safe_box": True,
            "width": 100,
            "row_styles": ['dim', ''],
            "title_style": "green"
        }
        config.update(overrides)
        return Table(**config)

    def _make_updater_get_albums_table(self, artist: CachedArtist = None):
        table = self._new_table()
        table.add_column("No.", width=10, style="green")
        table.add_column("Artist", width=35, style="green")
        table.add_column("MBID", width=40, style="green")
        table.add_column("Albums found", width=15, style="green")
        
        for r in self.albums:
            table.add_row(*r)
        return table

    def artist_albums_updated(self, artist: CachedArtist, count):
        self.albums.append((count, artist.artist_name, artist.artist_mbid, str(len(artist.albums))))
        self.albums = self.albums[-5:]
        self.live.update(self._make_updater_get_albums_table(artist))


"""
kwargs, interesting and going to be extremely useful: https://stackoverflow.com/questions/1769403/what-is-the-purpose-and-use-of-kwargs#:~:text=You%20can%20use%20**kwargs,passed%20to%20the%20function%20...
"""