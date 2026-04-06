from ..core.models import UpdaterConfig
from ..core.normalise import normalise
from .streamrip_client import StreamripClient
from .get_album_id import get_deezer_artist_id, get_deezer_album_id, get_fuzzy_deezer_album_id, get_album_name_from_id
from streamrip.progress import clear_progress
from streamrip.media import remove_artwork_tempdirs

from rich import print # so helpful when looking at printed dicts and lists oh my
import re
import logging
from pathlib import Path
import asyncio

"""
    - I'm beholden to what deezer provides and contains and so so there's some noise, some error and weird edge cases like +44/plus 44
      out of my small test music (60gb ish of the stuff) with 22 artists, with 18 missing studio albums, i find 15. 

      Jay-z's "the black album revisited", black sabbath's "studio outtakes" and 50 cent's "street king immortal" don't exist on deezer nor qobuz but do on musicbrains
      so I can't find album ids for them on the two major music downloaders. There will always just be *there*, I could add a "not on deezer"/"not on qobuz"
      column to the albums table and db querying so that I'm not attempting to find ids for albums which don't exist on the streaming services but then that's
      more overhead for very little cost. querying deezer is pretty cheap and adding an entire other attribute to the database for a minority occurances seems more
      expensive than I'm willing. Though if this becomes a guarenteed 1/4 chance then i'll look into it
"""

logger = logging.getLogger(__name__)

DEEZER_ARTIST_ALIASES = {
    "+44": "plus 44" # YIPPEE TIME TO ASK THE USER FOR INFORMATION EXCEPT THIS TIME THE USER HAS NO CLUE WHAT TO ALIAS IT WITH YIPPEEEE THANKS BAD DATA
}

def strip_year(s: str) -> tuple: # will be moved into normalise.py, can't use normalise_album in its current form as it breaks matches like:
    """ removes the year from a given local title """

    return re.sub(r'\([1-2][0-9][0-9][0-9]\)', "", s).strip() # "hip-hop showdown - 50 cent v snoop dogg (2019)"

# both the surrounding functions need to be moved into normalise.py and reduce the repetetive normalisation I do spread across multitple functions
# it's only this way right now because I'm dealing with so much data from so many sources and the same normalisation steps done to local files for example
# would completely wreck my shit when performing the same steps to deezer data 

def further_normalisation(s: str) -> str:
    """ removes any characters within parenthesis and the parenthesis """

    return re.sub(r"\s*\([^)]*\)\s*$", "", s).strip()

#def resolve_local_artist_dir(base_path: Path, artist: str) -> Path | None:
#    """ ensures the artist path exists locally, used to ensure artist from deezer matches artist locally """

#    target = normalise(artist)

#    for p in base_path.iterdir():
#        if not p.is_dir():
#            continue
#        if normalise(p.name) == target:
#            return p
#
#    return None # unused since adding fuzzy album query may still be useful in the future for qobuz querying

def get_source(upd_cfg: UpdaterConfig, missing_albums: dict[str, dict[str, list[str]]]):
    """ determines which download source to use """

    if upd_cfg.download_source.lower() == "deezer":
        to_download = get_deezer_ids(upd_cfg, missing_albums)

        for id in to_download:
            print(f"{id}: {get_album_name_from_id(id)}") # im lazy and having a quick way to confirm what gets found is awesome

        print(len(to_download))

        asyncio.run(run_downloads(upd_cfg, to_download))

async def run_downloads(upd_cfg: UpdaterConfig, to_download):
    sr_client = StreamripClient(upd_cfg)
    await sr_client.init_client()

    try:
        for id in to_download:
            await sr_client.deezer_rip(id)
    finally:
        await sr_client.close()
        clear_progress()
        remove_artwork_tempdirs()

def get_deezer_ids(upd_cfg: UpdaterConfig, missing_albums: dict[str, dict[str, list[str]]]) -> list[int]:
    """ builds list of missing album ids """

    to_download = []

    for artist, album_type in missing_albums.items():
        for a_type, m_albums in album_type.items():

            singles = True if a_type == "singles" else False
            allowed_types = {"single"} if singles else {"album", "albums"}

            missing_titles = [further_normalisation(normalise(strip_year(title))) for title in m_albums] # this mess is why i need a standardised normalise.py

            i = 0

            while True: # loops 5 times if the first 4 artists don't have any of what we're looking for, this is where resolve_local_artist_dir was used 
                        # as I could use the local collection to confirm if the artist was right but i just fuzzy search the albums anyway

                if i == 5:
                    break

                for k, v in DEEZER_ARTIST_ALIASES.items():
                    if artist in k: # same reverse matching method used in playlist module
                        search_artist = v # just not bi directional as the key is known bad
                    else:
                        search_artist = artist

                artist_id = get_deezer_artist_id(search_artist, i)

                if not artist_id:
                    logger.error("No artist id found for artist: %s", artist)
                    break

                albums = get_deezer_album_id(artist_id, index=0)

                remove_duplicates = {}
                found_titles = []

                for title, data in albums.items(): # deezer returns multiple albums of the same name but different id as they distinguish between explcit and non-explicit albums I
                    norm_title = further_normalisation(normalise(title)) # currently have it hard coded to prefer explicit albums shouldn't be too difficult to make it user definable

                    if data["record_type"] not in allowed_types:
                        continue # remove instances of singles of the same name as a studio album

                    if norm_title not in missing_titles:
                        continue

                    found_titles.append(norm_title)

                    if norm_title not in remove_duplicates:
                        remove_duplicates[norm_title] = data
                        continue

                    if not remove_duplicates[norm_title]["explicit_lyrics"] and data["explicit_lyrics"]: 
                        remove_duplicates[norm_title] = data

                # ids found from artist album listing
                matched_ids = [data["album_id"] for data in remove_duplicates.values()]

                print(matched_ids) # will be replaced with rich live table when i come to adding ui elements

                to_download.extend(matched_ids)

                still_missing = [t for t in missing_titles if t not in found_titles]

                for miss in still_missing: # fuzzy search for any albums that remain illusive (~mAntras~ and hell aint a bad place to be (in memory of bon scott))

                    fuzzy_results = get_fuzzy_deezer_album_id(miss, artist)

                    if not fuzzy_results:
                        continue

                    for res in fuzzy_results:
                        res_title = further_normalisation(normalise(res["title"]))

                        if miss not in res_title:
                            continue # sub string match missing name to deezer result, exact matching misses "the forever sessions (vol. 1)", I can comfortably rely on 
                            # the album name passed in from load_album.py as it's been through 7 levels of normalisation, the same place im going for making this tool :P

                        if res["record_type"] not in allowed_types:
                            continue # skip if its a single

                        if "artist_name" in res: # if everything else matches but its from a different artist, discard
                            if normalise(res["artist_name"]) != normalise(artist):
                                continue

                        to_download.append(res["id"])
                        break

                if matched_ids or still_missing:
                    #print(still_missing)
                    break

                i += 1
                logger.error("Bad match on artist: %s, trying again", artist)

    return to_download
                
"""
list comp with dictionary: https://stackoverflow.com/questions/27742537/list-comprehensions-extracting-values-from-a-dictionary-in-a-dictionary
    struggled on a clean way to handle it for a little
"""