> image_not_found (soon) (imagine some cool swiss army knife with music notes, film reel and clapperboard as the tools)

---

An automation tool used to aid in the management of self-hosted media services.

# Features
- A playlist tool which takes playlists from online music providers like [last.fm](https://www.last.fm) or `.csv` Spotify exports from [TuneMyMusic](https://www.tunemymusic.com/) and converts them to an `.m3u8` file, containing the correct paths for importing into [Navidrome](https://www.navidrome.org/) (or any other platforms that support `.m3u`/`.m3u8`).
    - From: `"Chic 'N' Stu","System Of A Down","Steal This Album!","Example Playlist","Playlist","USSM10213322","11i33j50Gsr90pRoDJBrEA"`
    - To: `/music/System Of A Down/System Of A Down - Steal This Album! (2002) [FLAC] [16B-44.1kHz]/01. System Of A Down - Chic 'N' Stu.flac`
    - A reletively robust search, it can match when spotify pairs a song to it's single release and only the album release is stored locally
    - Configurable blacklist/whitelist strings that allow for finer control over "(live)" or "(English ver.)" of songs

- A "cleaner" tool that will clean a download folder of empty/failed downloads and move an artist's albums into their artist directory, ready for transferring

- An "updater" tool that scans your local collection, build a local cache of each artist and their albums and allows you to compare locally what you have vs. what you're missing!
  - Highly customisable allowing for extreme granular control, to compare only given artists, ignoring artists from your collection entirely and remapping a potential bad match. 

- And more to come! (support for [Spotify](https://open.spotify.com/), [qobuz](https://www.qobuz.com), [deezer](https://www.deezer.com/) coming soon!)

# Installation
 <a href="https://pip.pypa.io/en/stable/installation/">pip</a>, <a href="https://git-scm.com/install/">git/Github Desktop</a> and <a href="https://www.python.org/downloads/">Python</a> 3.11.9 or greater is required.

> no pypi install as this is a niche tool, will work on it if requested

To download the latest stable release:
```
pip3 install git+https://github.com/naomisilver/mediamultitool.git@main
```
If you have a specific issue OR want to use the newest features, use:
```
pip3 install git+https://github.com/naomisilver/mediamultitool.git@dev
```

> Platform specific installation guidelines TBD

# Example usage

### `playlist`

Once downloaded, and you've entered `local_music_path` and edited `container_root` in `config.toml`. You can run:

The following will give a `.m3u8` file, with name of the Playlist name value in the csv data, in the location of the csv file.

```
mmt playlist "/path/to/csv_data.csv"
```

To process a last.fm playlist, supply a last.fm API key from [here](https://www.last.fm/api/authentication), and place it in `config.toml`, then, provided the playlist is public. You can do:

```
mmt playlist https://www.last.fm/user/example/playlists/playlistId
```

To output to a specific location, you can (otherwise the `default_output` value from config.toml will be used):

```
mmt playlist "/path/to/csv_data.csv" -o "/path/to/output"
```

To process an entire directory of `.csv` files, you can use the `-r` flag:

```
mmt playlist -r "/path/to/csv directory" "/path/to/output"
```

Or alternatively, you can process multiple `.csv` files by providing multiple input paths:

```
mmt playlist "/path/to/csv file 1" "/path/to/csv file 2" 
```

---

### `updater`

On first run of `mmt updater`, you will be instructed to run the following, this will generate the local cache to use in the comparison.

> depending on the size of your local collection, this may take some time. the source used to gather this data, limits the amount of queries to 1 per second. So, on first run it will be 1 second per artist and anywhere from 1-5 seconds per that artist's albums (artists with many releases require multiple queries)

```
mmt updater --update-cache
```

Following this command, it will show you a shortened list of what you're missing. This will generate a `.json` file that outlines exactly what is missing. However, may notice that one of the matches made is incorrect. You can run the following command to intiate a refresh:

```
mmt updater --refresh-artist <artist_name>
```

Now your local cache is accurate and up to date, you can compare your entire collection but ignoring any given artist(s) using the following:

```
mmt updater --excluding <artist_name> <artist_name>
```

Or you can compare only the given artist(s):

```
mmt updater --only <artist_name> <artist_name>
```

> This is only a brief foray into the potential uses for the current modules, for a deeper dive into all possible options and usages, see the [wiki](https://github.com/naomisilver/mediamultitool/wiki)

# Issues/feature requests/contributions
Any feedback or input is massively helpful, while I'm building this tool primarily for myself and my own use case, I've tried to build it as general purpose as possible. To submit an issue or feature request, see <a href="https://github.com/naomisilver/mediamultitool/issues">issues</a> and use the provided template.

---

# Roadmap
> This tool, as mentioned is earlier, is built for my own use case (and out of annoyance switching between self hosted platforms) and currently it does what *I* need it to do, that does not mean I'm against adding features I don't intend use.

- With [last.fm](https://www.last.fm) integration, I'm fairly confident I can now support qobuz playlist importing as I will need to use a very similar process. Deezer is not something I've looked too deeply into and spotify will require their API. Though none of this should be awfully difficult.
  - I'm unsure if Spotify can output JSON playlist data (I would suspect yes), I know they can provide CSV files but idk. 
- This program was intended as a sink for all my single use scripts I've made in the couple years but many of my non-music based scripts have been replaced by tools like filebot so don't have much of a place here anymore, and with all current future possible features being music related, this tool may get a name change :P
  - this is becoming more and more likely, there isn't really an alternative to this tool (that doesn't require paying for, or the self-hosted services to be publically accessible) and I feel bad bogging down a potentially incredibly useful tool with little things I want
