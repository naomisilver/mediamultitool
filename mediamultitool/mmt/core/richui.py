from .models import CachedArtist

from rich import box
from rich.console import Console, Group
from rich.table import Table
from rich.live import Live
from rich.prompt import Prompt

class RichUI:
    def __init__(self):
        self.albums_rows = []
        self.artist_rows = []
        self.missing_tracks = []
        self.matching_tracks = []
        self.current_artist_name = None

        self.con = Console()

        self.priority = {
            "studio_album": 4,
            "ep": 3,
            "single": 2,
            "compilation": 1,
            "live_album": 0,
        }

        self.live = None

    def start(self):
        if self.live:
            return
        self.live = Live(self.render(), refresh_per_second=4)
        self.live.start()

    def stop(self):
        if self.live:
            self.live.stop()
            self.live = None

    def ask(self, prompt: str) -> str:
        if self.live:
            self.live.stop() # moved prompt management to here so I can stop the live rendering so the table doesn't render overtop the prompt

        ans = Prompt.ask(prompt, console=self.con)

        self.start()
        self.refresh()
        return ans

    def render(self):
        renderables = []

        if self.artist_rows:
            renderables.append(self._make_static_artist_details_table())
        
        if self.albums_rows:
            renderables.append(self._make_updater_get_albums_table())

        if self.missing_tracks:
            renderables.append(self._make_missing_tracks_table())

        if self.matching_tracks:
            renderables.append(self._make_matching_tracks_table())

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

    def _make_updater_get_albums_table(self):
        table = self._new_table(title="Artists Updated")
        table.add_column("No.", width=10, style="green")
        table.add_column("Artist", width=35, style="green")
        table.add_column("MBID", width=40, style="green")
        table.add_column("Albums found", width=15, style="green")

        for r in self.albums_rows:
            table.add_row(*r) # .append(()) appends a tuple, *r unpacks the tuple

        return table

    def _make_static_artist_details_table(self):
        table = self._new_table(title=self.current_artist_name or "Artist Details")
        table.add_column("Title", width=60, style="green")
        table.add_column("Release Type", width=18, style="green")
        table.add_column("Release Date", width=18, style="green")

        for r in self.artist_rows:
            table.add_row(*r)

        return table
    
    def _make_matching_tracks_table(self):
        table = self._new_table(title="Matching Tracks")
        table.add_column(width=100, style="green")

        for r in self.matching_tracks:
            table.add_row(r)

        return table
    
    def _make_missing_tracks_table(self):
        table = self._new_table(title="Missing Tracks", title_style = "bold red")
        table.add_column("Artist", width=28, style="bold red")
        table.add_column("Album Title", width=28, style="bold red")
        table.add_column("Track Title", width=38, style="bold red")

        for r in self.missing_tracks:
            table.add_row(*r)

        return table

    def artist_albums_updated(self, a: CachedArtist, count: int):
        self.albums_rows.append((str(count), a.artist_name, a.artist_mbid, str(len(a.albums))))
        self.albums_rows = self.albums_rows[-5:]
        self.refresh()

    def static_artist_details(self, a: CachedArtist):
        self.current_artist_name = a.artist_name
        self.artist_rows = []

        sorted_albums = sorted(a.albums, key=lambda album: (self.priority.get(album['release_type'], 99),album['release_date']), reverse=True)

        count = 0
        for album in sorted_albums:
            truncated_album = (album['album_title'][:56] + ".." if len(album['album_title']) > 55 else album['album_title'])
            self.artist_rows.append((truncated_album, album['release_type'], album['release_date']))
            count = count + 1
            if count == 10:
                break

        self.refresh()

    def playlist_matching_tracks(self, path: str):
        self.matching_tracks.append(path)
        self.matching_tracks = self.matching_tracks[-5:]
        self.refresh()

    def playlist_missing_tracks(self, artist: str, album: str, track: str):
        try:
            t_artist = (artist[:26] + ".." if len(artist) > 24 else artist)
        except:
            t_artist = ""
        try:
            t_album = (album[:24] + ".." if len(album) > 24 else album)
        except:
            t_album = ""
        try:
            t_track = (track[:34] + ".." if len(track) > 34 else track)
        except:
            t_track = ""

        self.missing_tracks.append((t_artist, t_album, t_track))
        self.refresh()