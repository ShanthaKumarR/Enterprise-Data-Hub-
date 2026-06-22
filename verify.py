"""
verify.py
=========
Quick sanity-check query against the catalog database: prints each
container scanned, how many tables were found, and a sample of columns.
"""

from sqlalchemy.orm import sessionmaker

from models import CatalogContainer


def verify_catalog_contents(catalog_engine) -> None:
    """Print a summary of what's currently stored in the catalog database."""
    CatalogSession = sessionmaker(bind=catalog_engine)

    print("--- Verifying Catalog Contents ---")

    with CatalogSession() as session:
        containers = session.query(CatalogContainer).all()

        for c in containers:
            print(f"\nContainer: {c.container_name} (Scanned: {c.last_scanned_at})")
            print(f"Total Tables Tracked: {len(c.tables)}")

            if c.tables:
                sample_table = c.tables[0]
                print(f"  └─ Sample Table: {sample_table.table_name}")
                column_names = ", ".join(col.column_name for col in sample_table.columns[:5])
                print(f"     └─ Columns Found: {column_names}...")