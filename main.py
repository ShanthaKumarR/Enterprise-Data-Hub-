import io
import os
from pathlib import Path

import boto3
import pandas as pd
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from configuration.config import _build_db_config, _require_env, build_mysql_url
from configuration.connections import build_engine_registry, build_catalog_engine, run_health_check
from data_catalog.extractor import extract_all
from data_catalog.ingest import ingest_metadata
from data_catalog.models import create_catalog_schema, CatalogContainer
from data_catalog.verify import verify_catalog_contents

SOURCE_SYSTEMS = ['SOURCE_DB_1', 'SOURCE_DB_2', 'SOURCE_DB_3']
LOCAL_PARQUET_DIR = "./parquetfile"


def ensure_dir(dir_path: str):
    path = Path(dir_path)
    if path.exists():
        print(f"Directory '{dir_path}' already exists.")
        return
    path.mkdir(parents=True, exist_ok=True)
    print(f"Directory '{dir_path}' created.")


def get_tables_from_catalog(catalog_engine, source_db: str, fallback_schema: str) -> dict:
    """
    Look up which tables/columns belong to a source DB according to the catalog.
    Returns a dict of {table_name: {"schema": ..., "columns": [...]}}.
    """
    catalog_mapping = {}

    with Session(catalog_engine) as session:
        container = session.scalars(
            select(CatalogContainer).where(CatalogContainer.container_name == source_db)
        ).first()

        if not container:
            print(f"No container found in catalog for: {source_db}")
            return catalog_mapping

        for table in container.tables:
            table_name = getattr(table, 'table_name', None) or table.name
            table_columns = getattr(table, 'columns', None) or table.catalog_columns

            catalog_mapping[table_name] = {
                "schema": fallback_schema,
                "columns": [getattr(col, 'column_name', None) or col.name for col in table_columns],
            }

    return catalog_mapping


def extract_to_parquet(source: str, catalog_mapping: dict):
    """Pull every table listed in catalog_mapping out of `source` and drop it into S3 as parquet."""
    db_url = build_mysql_url(_build_db_config(source))
    if not db_url:
        print(f"Connection URI not found for: {source}")
        return

    source_engine = create_engine(db_url)
    s3_client = boto3.client(
        's3',
        aws_access_key_id=_require_env("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=_require_env("AWS_SECRET_ACCESS_KEY"),
        region_name=_require_env("AWS_DEFAULT_REGION"),
    )
    bucket = os.environ.get('S3_BUCKET')

    for table_name, details in catalog_mapping.items():
        columns = details.get("columns")
        if not columns:
            print(f"No columns found for table {table_name}, skipping.")
            continue

        schema = details.get("schema")
        full_table_name = f"`{schema}`.`{table_name}`" if schema else f"`{table_name}`"
        columns_str = ", ".join(f"`{col}`" for col in columns)
        query = text(f"SELECT {columns_str} FROM {full_table_name}")

        print(f"Extracting {table_name} from {source}...")
        try:
            with source_engine.connect() as conn:
                df = pd.read_sql_query(sql=query, con=conn)

            buffer = io.BytesIO()
            df.to_parquet(buffer, index=False, engine='pyarrow', compression='snappy')
            buffer.seek(0)

            s3_key = f"datalake/{source}/{table_name}.parquet"
            s3_client.upload_fileobj(Fileobj=buffer, Bucket=bucket, Key=s3_key)
        except Exception as e:
            print(f"Error processing table {table_name}: {e}")


def build_catalog():
    """Connect to every source container, pull schema metadata, and store it in the catalog DB."""
    engine_registry = build_engine_registry()
    catalog_engine = build_catalog_engine()
    print(f"Engine registry initialized with {len(engine_registry)} target databases.\n")
    run_health_check(engine_registry)

    metadata = extract_all(engine_registry)
    print(metadata)

    create_catalog_schema(catalog_engine)
    ingest_metadata(catalog_engine, metadata)
    verify_catalog_contents(catalog_engine)

    return catalog_engine


def dump_sources_to_parquet(catalog_engine):
    ensure_dir(LOCAL_PARQUET_DIR)
    for source in SOURCE_SYSTEMS:
        fallback_schema = _require_env(f"{source}_DATABASE")
        catalog_mapping = get_tables_from_catalog(catalog_engine, source, fallback_schema)
        extract_to_parquet(source, catalog_mapping)
        print('-' * 50)


def main():
    catalog_engine = build_catalog()
    dump_sources_to_parquet(catalog_engine)


if __name__ == "__main__":
    main()