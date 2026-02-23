"""
Pytest configuration — loads environment variables from frontend/.env
so that REACT_APP_BACKEND_URL is available to all tests.
"""
import os
from pathlib import Path


def pytest_configure(config):
    """Load .env files before tests run."""
    # Load backend .env
    backend_env = Path(__file__).parent.parent / ".env"
    if backend_env.exists():
        _load_dotenv(backend_env)

    # Load frontend .env for REACT_APP_BACKEND_URL
    frontend_env = Path(__file__).parent.parent.parent / "frontend" / ".env"
    if frontend_env.exists():
        _load_dotenv(frontend_env)


def _load_dotenv(path: Path):
    """Simple .env loader — does not override existing env vars."""
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key not in os.environ:
                    os.environ[key] = value
