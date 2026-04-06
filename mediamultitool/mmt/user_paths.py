from pathlib import Path
from platformdirs import user_config_dir, user_documents_dir

APP_NAME = "mediamultitool"
APP_DIR = Path(user_config_dir(APP_NAME))

CONFIG_PATH = APP_DIR / 'config.toml'
TEMPLATE_CONFIG_PATH = Path(__file__).parent.with_name("config.toml")

DB_PATH = APP_DIR / 'updater.db'
DL_DB_DIR = APP_DIR / 'downloads'

DOWNLOADS_DB_PATH = DL_DB_DIR / 'downloads.db'
FAILED_DOWNLOADS_DB_PATH = DL_DB_DIR / 'failed_downloads.db'

LOG_DIR = APP_DIR / "logs"
LOG_PATH = APP_DIR / "logs" / "mmt.log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

REPO_LINK = "https://github.com/naomisilver/mediamultitool"

DEFAULT_OUTPUT_DIR = Path(f"{user_documents_dir()}/{APP_NAME}")

DEFAULT_DOWNLOAD_DIR = DEFAULT_OUTPUT_DIR / 'downloads'

def ensure_paths():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    DL_DB_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

def ensure_default_output_path():
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)