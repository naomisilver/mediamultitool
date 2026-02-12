from ..models import Track, PlaylistConfig
from .search import search_music

from selenium import webdriver
from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import logging

"""
TODO:
    - I do need to look into a better console handler because this script causes it to look like its hanging when scraping the playlist data, 
        https://github.com/nathom/streamrip handles it really well, I'll need to take a look at their implementation
    - need to add checks for empty API key from pl_cfg
"""

API_ROOT = "https://ws.audioscrobbler.com/2.0/"

session = requests.Session()
logger = logging.getLogger(__name__)

def scrape_lastfm_playlist(url, pl_cfg):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("window-size=1,1500")

    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)

    wait = WebDriverWait(driver, 20)

    try:
        length_el = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "playlisting-playlist-length"))) # wait for the element showing playlist length to load

        playlist_name = driver.find_element(By.CSS_SELECTOR, ".playlisting-playlist-header-content h1").text # grab the text of the element showing playlist length

        excpected_count = int(length_el.text.split()[0]) # split it so you go from "115 tracks" to "115"

        last_count = 0

        while True: # last.fm using lazy loading zzz
            rows = driver.find_elements(By.CSS_SELECTOR, "tr.chartlist-row") # find all row elements (these contain the track data), overwrites itself as more of the page loads
            current_count = len(rows) # indexing based on the number of rows found

            if current_count >= excpected_count: # break out if the total number of tracks found matches the amount retrieved from the playlist-length element
                break

            if current_count == last_count: # if no new elements have been found
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);") # scroll

            last_count = current_count

        tracks = []

        for row in rows:
            track_name = row.find_element(By.CSS_SELECTOR, ".chartlist-name a").text # from each row find the track name
            artist_name = row.find_element(By.CSS_SELECTOR, ".chartlist-artist a").text # the artist name

            tracks.append(Track( # append the found data to a Track object
                track = track_name,
                album = None, # last.fm doesn't show this information on their playlist page so it isn't scrapable
                artist = artist_name
            ))

        album = get_album(tracks, pl_cfg, playlist_name) # keeping the call to get_album inside of the try catch block yes delays closing the browser instance
        # but keeping it outside causes (i think) the while loop to run forever and never timing out (because I haven't included it, can't account for playlists that are both
        # 2 tracks long and 4000 tracks long, a hardcoded timeout would hurt those with longer playlists)
    
    finally:
        driver.quit()

def fetch_lastfm_album(t, pl_cfg):
    artist_name = t.artist
    track_name = t.track

    headers = {
        'user-agent': "mediamultitool" # that's me! (so last.fm doesn't get angry)
    }

    payload = {
        "method": "track.getInfo", # last.fm's api method for getting track data
        "api_key": pl_cfg.lastfm_api_key, # the api_key provided in config.toml
        "artist": artist_name, # passing in the information pulled from scraping
        "track": track_name,
        "format": "json" # json format
    }
    r = session.get(API_ROOT, headers=headers, params=payload) # use the formerly created session to reuse the same TCP connections (connection pooling :D)

    data = r.json() # convert "response" object to a json/dictionary object
    album = data.get("track", {}).get("album", {}).get("title") # within "track {...album {title: "album_name"}...}"

    t.album = album # set album attribute in the passed Track object
    return t

def get_album(tracks, pl_cfg, playlist_name):
    full_track_data = []

    with ThreadPoolExecutor(max_workers=8) as executor: # opens a pool of 8 worker threads 
        futures = [executor.submit(fetch_lastfm_album, t, pl_cfg) for t in tracks] # queues all tasks and returns a "future", doesn't retain order can look at
        # ThreadPoolExecutor specific fix, or grabbing playlist number using selenium, adding it a Track attribute and then sorting using that. May be quicker
        for f in as_completed(futures): # retrieves only completed submit() runs
            full_track_data.append(f.result()) # appends only completed futures 

    for t in full_track_data:
        logger.debug("Retrieved: %s", f"{t.artist}, {t.album}, {t.track}") # i didn't expect this to work, passing in an formatted string to a "%s"? (I couldn't)
        # find a name for that operated, maybe it's also called a formatted string

    search_music(full_track_data, pl_cfg, playlist_name)

"""
    Sources/credit:
        - Scraping:                     https://proxy-seller.com/blog/how-to-scrape-spotify-playlist-data-using-python/ & https://www.selenium.dev/blog/2023/headless-is-going-away/
            - this may be for spotify but is exactly the same principle (headache trying to find the correct classes to scrape, take a look at the source
              for last.fm playlists if you want to know why). I *could* do the same with spotify but that requires API access, now I've managed it with
              last.fm it isn't off the cards anymore. though I will still likely keep csv as an option for bulk conversions
            - I was considering actually doing what the guide says and scraping spotify playlists but it supposedly obfuscates class
              names and changes them regularly so I can't rely on that. I could look at using their API in the future which would mean
              no more exporting a csv just grab a spotify playlist
        - Selenium explicit waits:      https://selenium-python.readthedocs.io/waits.html
        - last.fm with requests:        https://www.dataquest.io/blog/last-fm-api-python/
        - request sessions:             https://www.reddit.com/r/learnpython/comments/62746y/how_to_use_requestssession/
        - parallelising requests:       https://www.reddit.com/r/learnpython/comments/qdi69k/parallel_requests_in_python/ & https://docs.python.org/3/library/concurrent.futures.html#threadpoolexecutor-example
            - prior the above optimisations I was running 7~ secs to scrape for playlist data and 60~ secs for sequential lastfm api requests through pylast, 
              down to 30 secs for lastfm api requests switching from pylast to requests with session pooling, then down to 2.5~ secs parallelising the requests
              (with my test playlist containing 115 tracks)
            - unfortunately, scouring lastfm api methods (https://www.last.fm/api/intro) they don't expose actual playlist information, the api is appears
              to be primarily used for scrobbling and music metadata. Nope *they did*, https://www.last.fm/api/playlists. It would've meant I could just
              grab the playlist id from a provided URL and use only last.fm's API to get all the information I need :D but life is never easy

"""