from pathlib import Path
from platformdirs import user_config_dir, user_documents_dir

APP_NAME = "mediamultitool"
APP_DIR = Path(user_config_dir(APP_NAME))

CONFIG_PATH = APP_DIR / 'config.toml'
TEMPLATE_CONFIG_PATH = Path(__file__).parent.with_name("config.toml")

DB_PATH = APP_DIR / 'updater.db'

LOG_DIR = APP_DIR / "logs"
LOG_PATH = APP_DIR / "logs" / "mmt.log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

REPO_LINK = "https://github.com/naomisilver/mediamultitool"

DEFAULT_OUTPUT_DIR = Path(user_documents_dir() + APP_NAME)

def ensure_paths():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)