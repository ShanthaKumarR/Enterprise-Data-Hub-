"""
extractor.py
============
Introspects a database engine's schema (tables, columns, primary keys) and
returns it as a plain-data structure suitable for caching or ingestion.
"""

from sqlalchemy import inspect


def extract_container_metadata(engine) -> list:
    """
    Inspect all tables in the given engine and return a list of dicts:
        [{"table_name": ..., "columns": [{"column_name", "data_type",
                                           "is_nullable", "is_primary_key"}]}]
    """
    inspector = inspect(engine)
    schema_manifest = []
    table_names = inspector.get_table_names()

    for table in table_names:
        pk_constraint = inspector.get_pk_constraint(table)
        primary_keys = pk_constraint.get("constrained_columns", [])

        columns_info = inspector.get_columns(table)
        table_columns = []
        for col in columns_info:
            table_columns.append({
                "column_name": col["name"],
                "data_type": str(col["type"]),  # e.g. 'VARCHAR(50)'
                "is_nullable": col["nullable"],
                "is_primary_key": col["name"] in primary_keys,
            })

        schema_manifest.append({
            "table_name": table,
            "columns": table_columns,
        })

    return schema_manifest


def extract_all(engine_registry: dict) -> dict:
    """Run extract_container_metadata across every engine in the registry."""
    global_metadata_catalog = {}

    print("--- Starting Metadata Extraction ---")
    for container_name, engine in engine_registry.items():
        print(f"Scanning structure for: {container_name}...")
        try:
            global_metadata_catalog[container_name] = extract_container_metadata(engine)
            print(f"  ✓ Extracted {len(global_metadata_catalog[container_name])} tables successfully.")
        except Exception as e:
            print(f"  ✗ Failed to extract metadata from {container_name}: {e}")

    print("\nExtraction complete!")
    return global_metadata_catalog