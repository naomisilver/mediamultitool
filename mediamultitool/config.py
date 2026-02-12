from platformdirs import user_config_dir
from dataclasses import dataclass, field, fields, is_dataclass
from shutil import copy
from pathlib import Path

import logging
import tomlkit


APP_NAME = "mediamultitool"
logger = logging.getLogger(__name__)

"""
    TODO:
        - I want to rewrite this script, I've drawn too heavy of inspiration from streamrip's config file when I need to learn more about toml as an utility
"""

CONFIG_DIR = Path(user_config_dir(APP_NAME))
TEMPLATE_CONFIG_PATH = Path(__file__).with_name("config.toml")
CONFIG_FILE = CONFIG_DIR / "config.toml"

@dataclass(slots=True)
class APIKeys:
    lastfm_api_key: str = ''

@dataclass(slots=True)
class PlaylistConfig:
    container_root: str = '/music/'
    local_music_path: str = ''
    blocklist_strings: str = ''
    allowlist_strings: str = ''
    default_output: str = ''

@dataclass(slots=True)
class CleanerConfig:
    download_path: str = ''

@dataclass(slots=True)
class Misc:
    version: str = '0.1.2'

@dataclass(slots=True)
class AppConfig:
    apis: APIKeys = field(default_factory=APIKeys)
    playlist: PlaylistConfig = field(default_factory=PlaylistConfig)
    cleaner: CleanerConfig = field(default_factory=CleanerConfig)
    misc: Misc = field(default_factory=Misc)


def toml_from_config(config) -> tomlkit.items.Table:
    """ create toml table from dataclasses """
    table = tomlkit.table()

    for f in fields(config):
        value = getattr(config, f.name)

        if is_dataclass(value):
            table[f.name] = toml_from_config(value)
        else:
            table[f.name] = value

    return table


def config_from_toml(cls, toml_section):
    kwargs = {}

    for f in fields(cls):
        if f.name not in toml_section:
            continue

        raw = toml_section[f.name]

        if is_dataclass(f.type):
            kwargs[f.name] = config_from_toml(f.type, raw)
        else:
            value = raw.value if hasattr(raw, "value") else raw
            kwargs[f.name] = f.type(value)

    return cls(**kwargs)


def sync_config_to_toml(toml_section, config) -> bool:
    """ ensures current config on disk is up to date with config in code """
    changed = False

    for f in fields(config):
        value = getattr(config, f.name)

        if f.name not in toml_section:
            if is_dataclass(value):
                toml_section[f.name] = toml_from_config(value)
            else:
                toml_section[f.name] = value
            changed = True
        elif is_dataclass(value):
            changed |= sync_config_to_toml(
                toml_section[f.name],
                value
            )

    return changed

def load_config() -> AppConfig:
    """ load the config and create if it doesn't exist """

    if not CONFIG_FILE.exists():
        copy(TEMPLATE_CONFIG_PATH, CONFIG_DIR)

    doc = tomlkit.parse(CONFIG_FILE.read_text())

    if "app" not in doc:
        doc["app"] = tomlkit.table()

    root = doc["app"]

    cfg = config_from_toml(AppConfig, root)

    if sync_config_to_toml(root, cfg):
        CONFIG_FILE.write_text(tomlkit.dumps(doc))

    return cfg

def open_config():
    print()

"""
    Sources/credit:
        - Heavily inspired by: https://github.com/nathom/streamrip/blob/dev/streamrip/config.py
            - new to making python packages and toml as a config format, dataclass etc... 
"""
