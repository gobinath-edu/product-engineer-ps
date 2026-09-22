from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = DATA_DIR / "memory.db"

DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

APP_NAME = "Trustworthy Long-Term Memory"
APP_VERSION = "1.0.0"