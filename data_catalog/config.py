"""
=========
Loads database connection settings from environment variables (via a .env
file in local development, or real environment variables in production).

No credentials are hardcoded here — this module only assembles config dicts
and connection URLs from values supplied externally.
"""

import os
from dotenv import load_dotenv

# Load variables from a .env file (if present) into the process environment.
# In production, real environment variables take precedence and .env can be
# omitted entirely.
load_dotenv()


def _require_env(key: str) -> str:
    """Fetch an environment variable, failing loudly if it's missing."""
    value = os.environ.get(key)
    if value is None or value == "":
        raise EnvironmentError(
            f"Missing required environment variable: {key}. "
            f"Did you create a .env file from .env.example?"
        )
    return value


def _build_db_config(prefix: str) -> dict:
    """Build a single database config dict from a set of PREFIX_* env vars."""
    return {
        "host": _require_env(f"{prefix}_HOST"),
        "port": int(_require_env(f"{prefix}_PORT")),
        "user": _require_env(f"{prefix}_USER"),
        "password": _require_env(f"{prefix}_PASSWORD"),
        "database": _require_env(f"{prefix}_DATABASE"),
    }


def build_mysql_url(config: dict) -> str:
    """Build a SQLAlchemy MySQL connection URL from a config dict."""
    return (
        f"mysql+mysqlconnector://{config['user']}:{config['password']}"
        f"@{config['host']}:{config['port']}/{config['database']}"
    )


# --- Source databases to scan for schema metadata ---
CONTAINER_CONFIGS = {
    "source_db_1": _build_db_config("SOURCE_DB_1"),
    "source_db_2": _build_db_config("SOURCE_DB_2"),
    "source_db_3": _build_db_config("SOURCE_DB_3"),
}

# --- Central catalog database where extracted metadata is stored ---
CATALOG_DB_CONFIG = _build_db_config("CATALOG_DB")