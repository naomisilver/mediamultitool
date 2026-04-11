from .models import CachedArtist

from rich import box
from rich.console import Console, Group
from rich.table import Table
from rich.live import Live
from rich.prompt import Prompt
from rich.text import Text

class RichUI:
    def __init__(self):
        self.albums_rows = []
        self.artist_rows = []
        self.missing_tracks = []
        self.matching_tracks = []
        self.missing_albums = []
        self.matching_ids = []
        self.current_artist_name = None

        self.con = Console()

        self.priority = {
            "studio_album": 4,
            "ep": 3,
            "single": 2,
            "compilation": 1,
            "live_album": 0,
        }

        self.info_style = "bold green" # experiementing with colours and I feel these are the best for successes, missing and like *big missing*
        self.warning_style = "bold yellow"
        self.error_style = "bold red"

        self.live = None

    def start(self):
        """ starts a Live instance """

        if self.live:
            return
        self.live = Live(self.render(), refresh_per_second=4)
        self.live.start()

    def stop(self):
        """ stops current Live instance """

        if self.live:
            self.live.stop()
            self.live = None

    def ask(self, prompt: str) -> str:
        """ wrapper for rich.Prompt.ask """

        if self.live:
            self.live.stop() # moved prompt management to here so I can stop the live rendering so the table doesn't render overtop the prompt

        ans = Prompt.ask(prompt, console=self.con)

        self.start()
        self.refresh()
        return ans

    def render(self):
        """ Live renderer """

        renderables = []

        if self.artist_rows:
            renderables.append(self._make_static_artist_details_table())
        
        if self.albums_rows:
            renderables.append(self._make_updater_get_albums_table())

        if self.missing_tracks:
            renderables.append(self._make_missing_tracks_table())

        if self.matching_tracks:
            renderables.append(self._make_matching_tracks_table())

        if self.missing_albums:
            renderables.append(self._make_missing_albums_table())

        if self.matching_ids:
            renderables.append(self._make_matched_album_ids_table())

        return Group(*renderables)

    def refresh(self):
        """ refresh Live renderer """

        self.live.update(self.render())

    def _new_table(self, **overrides):
        """ table template where all creation methods derive from """

        config = {
            "box": box.ROUNDED,
            "safe_box": True,
            "width": 100,
            "row_styles": ['dim', '']
        }
        config.update(overrides)
        return Table(**config)

    def _make_updater_get_albums_table(self):
        """ table creation for mmt updater -u/--update-cache """

        table = self._new_table(title="Artists Updated", title_style=self.info_style)
        table.add_column("No.", width=10, style=self.info_style, header_style=self.info_style)
        table.add_column("Artist", width=35, style=self.info_style, header_style=self.info_style)
        table.add_column("MBID", width=40, style=self.info_style, header_style=self.info_style)
        table.add_column("Albums found", width=15, style=self.info_style, header_style=self.info_style)

        for r in self.albums_rows:
            table.add_row(*r) # .append(()) appends a tuple, *r unpacks the tuple

        return table

    def _make_static_artist_details_table(self):
        """ table creation for artist details for mmt updater -r/--refresh-artist """

        table = self._new_table(title=self.current_artist_name or "Artist Details", title_style = self.info_style)
        table.add_column("Title", width=66, style=self.info_style, header_style=self.info_style)
        table.add_column("Release Type", width=14, style=self.info_style, header_style=self.info_style)
        table.add_column("Release Date", width=14, style=self.info_style, header_style=self.info_style)

        for r in self.artist_rows:
            table.add_row(*r)

        return table
    
    def _make_matching_tracks_table(self):
        """ table creation matching tracks for mmt playlist ... """

        table = self._new_table(title="Matching Tracks", title_style = self.info_style)
        table.add_column(width=100, style=self.info_style, header_style=self.info_style)

        for r in self.matching_tracks:
            table.add_row(r)

        return table
    
    def _make_missing_tracks_table(self):
        """ table creation missing tracks for mmt playlist ... """

        table = self._new_table(title="Missing Tracks", title_style = self.warning_style)
        table.add_column("Artist", width=28, style=self.warning_style, header_style=self.warning_style)
        table.add_column("Album Title", width=28, style=self.warning_style, header_style=self.warning_style)
        table.add_column("Track Title", width=38, style=self.warning_style, header_style=self.warning_style)

        for r in self.missing_tracks:
            table.add_row(*r)

        return table
    
    def _make_missing_albums_table(self):
        """ table creation for missing albums both for mmt updater -p/--print and mmt updater """

        needs_suffix = any(len(r) == 4 for r in self.missing_albums)

        table = self._new_table(title="Missing Albums", title_style=self.warning_style)
        table.add_column("Artist", width=28, style=self.warning_style, header_style=self.warning_style)
        table.add_column("Album Title", width=52 if not needs_suffix else 43, style=self.warning_style, header_style=self.warning_style)

        if needs_suffix:
            table.add_column("", width=7, style=self.warning_style, header_style=self.warning_style)

        table.add_column("Release Type", width=14, style=self.warning_style, header_style=self.warning_style)

        for r in self.missing_albums:
            table.add_row(*r)

        return table
    
    def _make_matched_album_ids_table(self):
        """ table creation for matched album ids for mmt updater -d/--download """

        table = self._new_table(title="Matched IDs", title_style = self.info_style)
        table.add_column("Artist", width=28, style=self.warning_style, header_style=self.info_style, no_wrap=True)
        table.add_column("ID(s)", width=18, style=self.warning_style, header_style=self.info_style, no_wrap=True)
        table.add_column("Album Title", width=48, style=self.warning_style, header_style=self.info_style, no_wrap=True)

        for r in self.matching_ids:
            table.add_row(*r)

        return table

    def matched_album_ids(self, artist_name: str, album: dict, title: str):

        self.matching_ids.append((artist_name, str(album["album_id"]), title))
        self.matching_ids = self.matching_ids[-5:]
        self.refresh()

    def artist_albums_updated(self, a: CachedArtist, count: int):
        """ row logic for updating the local cache for mmt updater -u/--update-cache limited to 5 most recent gets """

        self.albums_rows.append((str(count), a.artist_name, a.artist_mbid, str(len(a.albums))))
        self.albums_rows = self.albums_rows[-5:]
        self.refresh()

    def static_artist_details(self, a: CachedArtist, t_title: str = None):
        """ row logic for static artist details for mmt updater -r/--refresh-artist """

        self.current_artist_name = t_title or a.artist_name
        self.artist_rows = []

        sorted_albums = sorted(a.albums, key=lambda album: (self.priority.get(album['release_type'], 99),album['release_date']), reverse=True)

        count = 0
        for album in sorted_albums:
            truncated_album = (album['album_title'][:63] + ".." if len(album['album_title']) > 65 else album['album_title'])
            self.artist_rows.append((truncated_album, album['release_type'], album['release_date']))
            count = count + 1
            if count == 10:
                break

        self.refresh()

    def playlist_matching_tracks(self, path: str):
        """ row logic for matching tracks for mmt playlist ... limited to 5 most recent matches"""

        self.matching_tracks.append(path)
        self.matching_tracks = self.matching_tracks[-5:]
        self.refresh()

    def playlist_missing_tracks(self, artist: str, album: str, track: str):
        """ row logic for missing tracks for mmt playlist ... """

        try:
            t_artist = (artist[:26] + ".." if len(artist) > 24 else artist)
        except:
            t_artist = ""
        try:
            t_album = (album[:24] + ".." if len(album) > 24 else album)
        except: # this feels awfully messy but when getting playlist information back from last.fm, it sometimes doesn't include the album. I hadn't run into an issue where
            t_album = "" # the artist and track title were missing but better safe than sorry
        try:
            t_track = (track[:34] + ".." if len(track) > 34 else track)
        except:
            t_track = ""

        self.missing_tracks.append((t_artist, t_album, t_track))
        self.refresh()

    def updater_missing_albums_one(self, artist_name: str, missing: list[str], album_type: str):
        """ row logic for mmt updater """

        truncated_artist = (artist_name[:25] + ".." if len(artist_name) > 27 else artist_name) # truncation/subscripting is crazy fun
        for m in missing:
            truncated_album = m[:40] + ".." if len(m) > 42 else m
            suffix = ""
            if len(missing) != 1:
                suffix = f"+ {len(missing)}"             

            self.missing_albums.append((truncated_artist, truncated_album, suffix, album_type))
            self.refresh()
            break # stop after the first album

    def updater_missing_albums_all(self, artist_name: str, missing: list[str], album_type: str):
        """ row logic for mmt updater -p/--print """

        truncated_artist = (artist_name[:25] + ".." if len(artist_name) > 27 else artist_name)
        for m in missing:
            truncated_album = m[:48] + ".." if len(m) > 50 else m

            self.missing_albums.append((truncated_artist, truncated_album, album_type))
            self.refresh()

"""
    - kwargs, interesting and going to be extremely useful: https://stackoverflow.com/questions/1769403/what-is-the-purpose-and-use-of-kwargs#:~:text=You%20can%20use%20**kwargs,passed%20to%20the%20function%20
    - rich:     https://rich.readthedocs.io/en/latest/tables.html
        - rich is awesome omg

    - sorting list based on priority:   https://www.geeksforgeeks.org/python/python-sort-list-according-to-other-list-order/
                                        https://stackoverflow.com/questions/4233476/sort-a-list-by-multiple-attributes
"""