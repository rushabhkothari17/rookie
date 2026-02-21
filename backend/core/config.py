"""Environment-backed configuration. All secrets/env values load here."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / ".env")


# ---- Database ------------------------------------------------------------
MONGO_URL: str = os.environ["MONGO_URL"]
DB_NAME: str = os.environ["DB_NAME"]

# ---- Auth ----------------------------------------------------------------
JWT_SECRET: str = os.environ["JWT_SECRET"]

# ---- Payments ------------------------------------------------------------
STRIPE_API_KEY: str = os.environ.get("STRIPE_API_KEY", "")

# ---- Admin seed ----------------------------------------------------------
ADMIN_EMAIL: str = os.environ.get("ADMIN_EMAIL", "")
ADMIN_PASSWORD: str = os.environ.get("ADMIN_PASSWORD", "")

# ---- GoCardless ----------------------------------------------------------
GOCARDLESS_ACCESS_TOKEN: str = os.environ.get("GOCARDLESS_ACCESS_TOKEN", "")
GOCARDLESS_ENVIRONMENT: str = os.environ.get("GOCARDLESS_ENVIRONMENT", "sandbox")

# ---- App -----------------------------------------------------------------
APP_URL: str = os.environ.get("REACT_APP_BACKEND_URL", "").replace("/api", "").rstrip("/")
