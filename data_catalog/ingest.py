"""
ingest.py
=========
Takes the in-memory metadata catalog (produced by extractor.extract_all)
and persists it into the catalog database using the ORM models.
"""

from sqlalchemy.orm import sessionmaker

from data_catalog.models import CatalogContainer, CatalogTable, CatalogColumn


def ingest_metadata(catalog_engine, global_metadata_catalog: dict) -> None:
    """
    Persist the scanned metadata into the catalog database.

    global_metadata_catalog: {container_name: [{"table_name", "columns": [...]}]}
    as produced by extractor.extract_all().
    """
    CatalogSession = sessionmaker(autocommit=False, autoflush=False, bind=catalog_engine)

    print("--- Starting Metadata Ingestion into Catalog DB ---")

    with CatalogSession() as session:
        try:
            for container_name, tables_list in global_metadata_catalog.items():
                print(f"Ingesting catalog data for: {container_name}...")

                db_container = CatalogContainer(container_name=container_name)
                session.add(db_container)

                for table_data in tables_list:
                    db_table = CatalogTable(table_name=table_data["table_name"])
                    db_container.tables.append(db_table)

                    for col_data in table_data["columns"]:
                        db_column = CatalogColumn(
                            column_name=col_data["column_name"],
                            data_type=col_data["data_type"],
                            is_nullable=col_data["is_nullable"],
                            is_primary_key=col_data["is_primary_key"],
                        )
                        db_table.columns.append(db_column)

            session.commit()
            print("\n✓ Success! All metadata has been saved into the Central Catalog Database.")

        except Exception as e:
            session.rollback()
            print(f"\n✗ Ingestion failed! Rolling back changes. Error: {e}")
            raise