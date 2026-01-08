import os
from . import limits

APP_NAME = os.getenv("APP_NAME", "ae2-collector")
LOG_RAW = os.getenv("LOG_RAW", "0") == "1"
MAX_ITEMS = int(os.getenv("MAX_ITEMS", "200000"))
GCS_BUCKET = os.getenv("GCS_BUCKET", "")
GCS_PREFIX = os.getenv("GCS_PREFIX", "raw")
DASHBOARD_TOP_N = limits.API_MAX
DEFAULT_WORLD_ID = os.getenv("DEFAULT_WORLD_ID", "atm9")
MIN_DT_SEC = float(os.getenv("MIN_DT_SEC", "10"))
