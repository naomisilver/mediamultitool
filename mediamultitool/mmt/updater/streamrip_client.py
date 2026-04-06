from ..core.models import UpdaterConfig
from ..user_paths import DOWNLOADS_DB_PATH, FAILED_DOWNLOADS_DB_PATH, DEFAULT_DOWNLOAD_DIR

import asyncio

from streamrip.client import DeezerClient
from streamrip.config import Config
from streamrip.media import PendingAlbum
from streamrip.db import Dummy
from streamrip import db

class StreamripClient(): # a look into the pattern this entire package will follow in the future

    def __init__(self, upd_cfg: UpdaterConfig):
    
        self.config = Config.defaults()

        self.downloads_db = db.Downloads(str(DOWNLOADS_DB_PATH))
        self.failed_db = db.Failed(str(FAILED_DOWNLOADS_DB_PATH))

        #self.db = db.Database(self.downloads_db, self.failed_db) # won't redownload albums that have already been downloaded, diverged from the streamrip docs for this
        self.db = db.Database(downloads=Dummy(), failed=Dummy()) # and followed the same pattern they used in rip/main.py to use the same db they use. I *could* combine this
        # with the db created when streamrip is installed as a global package so that I share the same downloads, would be as easy as chaning the global file paths

        self.config.session.downloads.folder = str(DEFAULT_DOWNLOAD_DIR)
        
        if upd_cfg.download_source.lower() == "deezer":
            self.config.session.deezer.arl = upd_cfg.deezer_arl_token
            self.config.session.deezer.quality = 0

            self.c = DeezerClient(self.config)

    async def init_client(self):

        await self.c.login()

    async def deezer_rip(self, id: int):

        p = PendingAlbum(id, self.c, self.config, self.db)
        resolved_album = await p.resolve()

        await resolved_album.rip()

    async def close(self):
        if hasattr(self.c, "session"):
            await self.c.session.close()

"""
    - streamrip scripting docs: https://github.com/nathom/streamrip/wiki/Scripting-with-Streamrip-v2
    - db usage:                 https://github.com/nathom/streamrip/blob/dev/streamrip/rip/main.py
"""