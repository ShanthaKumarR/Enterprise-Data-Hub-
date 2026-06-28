import io
import os
from pathlib import Path

import boto3
import pandas as pd
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from configuration.config import _build_db_config, _require_env, build_mysql_url
from configuration.connections import build_catalog_engine
from data_catalog.models import CatalogContainer

SOURCE_SYSTEMS = ['SOURCE_DB_1', 'SOURCE_DB_2', 'SOURCE_DB_3']
LOCAL_PARQUET_DIR = "./parquetfile"

catalog_engine = build_catalog_engine()


def ensure_dir(dir_path: str):
    path = Path(dir_path)
    if path.exists():
        print(f"Directory '{dir_path}' already exists.")
    else:
        path.mkdir(parents=True, exist_ok=True)
        print(f"Directory '{dir_path}' created.")


def get_tables_from_catalog(catalog_engine, source_db: str, fallback_schema: str) -> dict:
    """Pull the table/column list for a given source DB out of the catalog."""
    catalog_mapping = {}

    with Session(catalog_engine) as session:
        stmt = select(CatalogContainer).where(CatalogContainer.container_name == source_db)
        container = session.scalars(stmt).first()

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
    """Read each table for `source` and push it to S3 as parquet."""
    db_dns = build_mysql_url(_build_db_config(source))
    if not db_dns:
        print(f"Connection URI not found for: {source}")
        return

    target_engine = create_engine(db_dns)

    s3_client = boto3.client(
        's3',
        aws_access_key_id=_require_env("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=_require_env("AWS_SECRET_ACCESS_KEY"),
        region_name=_require_env("AWS_DEFAULT_REGION"),
    )

    bucket = os.environ.get('S3_BUCKET')

    for table_name, details in catalog_mapping.items():
        schema = details.get("schema")
        columns = details.get("columns")

        if not columns:
            print(f"No columns found for table {table_name}, skipping.")
            continue

        columns_str = ", ".join(f"`{col}`" for col in columns)
        full_table_name = f"`{schema}`.`{table_name}`" if schema else f"`{table_name}`"
        query = f"SELECT {columns_str} FROM {full_table_name}"

        print(f"Extracting {table_name} from {source}...")
        try:
            with target_engine.connect() as conn:
                df = pd.read_sql_query(sql=text(query), con=conn)

            buffer = io.BytesIO()
            df.to_parquet(buffer, index=False, engine='pyarrow', compression='snappy')
            buffer.seek(0)

            s3_key = f"datalake/{source}/{table_name}.parquet"
            s3_client.upload_fileobj(Fileobj=buffer, Bucket=bucket, Key=s3_key)

        except Exception as e:
            print(f"Error processing table {table_name}: {e}")


def main():
    ensure_dir(LOCAL_PARQUET_DIR)

    for source in SOURCE_SYSTEMS:
        fallback_schema = _require_env(f"{source}_DATABASE")
        catalog_mapping = get_tables_from_catalog(catalog_engine, source, fallback_schema)
        extract_to_parquet(source, catalog_mapping)
        print('-' * 50)


if __name__ == '__main__':
    main()