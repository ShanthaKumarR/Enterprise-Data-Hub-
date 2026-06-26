"""
=======
Orchestrates the full pipeline:
  1. Build engines for source containers + catalog DB, health-check them.
  2. Extract schema metadata from every source container.
  3. Create the catalog schema (if needed).
  4. Ingest extracted metadata into the catalog database.
  5. Verify what's now stored in the catalog.

Run with:  python main.py
"""

from data_catalog.connections import build_engine_registry, build_catalog_engine, run_health_check
from data_catalog.extractor import extract_all
from data_catalog.models import create_catalog_schema
from data_catalog.ingest import ingest_metadata
from data_catalog.verify import verify_catalog_contents


def main():
    # 1. Connect to source containers + catalog DB
    engine_registry = build_engine_registry()
    catalog_engine = build_catalog_engine()
    print(f"Engine registry initialized with {len(engine_registry)} target databases.\n")
    run_health_check(engine_registry)

    # 2. Extract schema metadata from every source container
    global_metadata_catalog = extract_all(engine_registry)

    # 3. Ensure the catalog schema exists
    create_catalog_schema(catalog_engine)

    # 4. Ingest extracted metadata into the catalog database
    ingest_metadata(catalog_engine, global_metadata_catalog)

    # 5. Verify what's stored
    verify_catalog_contents(catalog_engine)


if __name__ == "__main__":
    main()