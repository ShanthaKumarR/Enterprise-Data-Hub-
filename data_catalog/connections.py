"""
==============
Builds SQLAlchemy engines for every source container plus the catalog
database, and provides a health check to verify they're reachable.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from config import CONTAINER_CONFIGS, CATALOG_DB_CONFIG, build_mysql_url


def build_engine_registry() -> dict:
    """Create one SQLAlchemy engine per source container."""
    return {
        name: create_engine(build_mysql_url(cfg), pool_pre_ping=True)
        for name, cfg in CONTAINER_CONFIGS.items()
    }


def build_catalog_engine():
    """Create the SQLAlchemy engine for the central catalog database."""
    return create_engine(build_mysql_url(CATALOG_DB_CONFIG))


def run_health_check(engine_registry: dict) -> None:
    """Run a lightweight SELECT 1 against every engine to confirm connectivity."""
    print("--- Running Connection Health Check ---")
    for name, engine in engine_registry.items():
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            print(f"✓ {name}: Connected successfully.")
        except OperationalError as e:
            print(f"✗ {name}: Connection failed! Is the container running on that port?")
            print(f"   [Error Details]: {e.orig if hasattr(e, 'orig') else e}")