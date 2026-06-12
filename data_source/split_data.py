"""
classicmodels_export.py

Exports tables from a MySQL `classicmodels` database into per-database SQL
init scripts. Each generated script creates a target database, its tables
(DDL), and populates them with INSERT statements sourced from the live DB.

Output structure:
    init-scripts/
        sales_db.sql      -- customers, orders, orderdetails, payments
        products_db.sql   -- products, productlines
        hr_db.sql         -- employees, offices

Usage:
    Configure the DB connection constants below, then run:
        python classicmodels_export.py

Requirements:
    pip install sqlalchemy mysql-connector-python
"""

from pathlib import Path

from sqlalchemy import create_engine, text


# ---------------------------------------------------------------------------
# Database connection settings
# ---------------------------------------------------------------------------

HOST     = "localhost"
PORT     = 3306
USER     = "root"
PASSWORD = "root"
SOURCE   = "classicmodels"

SRC_URL = f"mysql+mysqlconnector://{USER}:{PASSWORD}@{HOST}:{PORT}/{SOURCE}"

# ---------------------------------------------------------------------------
# Export blueprint: maps each target database to the tables it should contain
# ---------------------------------------------------------------------------

DB_BLUEPRINTS: dict[str, list[str]] = {
    "sales_db":    ["customers", "orders", "orderdetails", "payments"],
    "products_db": ["products", "productlines"],
    "hr_db":       ["offices", "employees"],
}

OUTPUT_DIR = "init-scripts"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ensure_directory(dir_name: str) -> Path:
    """Create *dir_name* relative to this script's location if it doesn't exist.

    Args:
        dir_name: Name of the directory to create (relative to the script).

    Returns:
        The resolved :class:`~pathlib.Path` of the target directory.

    Raises:
        NotADirectoryError: If *dir_name* already exists as a regular file.
    """
    target = Path(__file__).resolve().parent / dir_name

    if target.exists():
        if not target.is_dir():
            raise NotADirectoryError(
                f"'{target}' already exists but is a file, not a directory."
            )
        print(f"Directory already exists: {target}")
    else:
        target.mkdir(parents=True, exist_ok=True)
        print(f"Directory created: {target}")

    return target


def format_sql_value(value) -> str:
    """Render a Python value as a SQL literal suitable for an INSERT statement.

    * ``None``  → ``NULL``
    * ``int`` / ``float`` → bare numeric string
    * Everything else → single-quoted string with internal single quotes escaped.

    Args:
        value: The Python value to format.

    Returns:
        A SQL-safe string representation of *value*.
    """
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def write_table(file, connection, table: str) -> None:
    """Write the DDL and INSERT data for *table* into *file*.

    Fetches the ``CREATE TABLE`` statement via ``SHOW CREATE TABLE`` and
    dumps all rows as a single multi-row ``INSERT`` statement.  If the
    table is empty only the DDL is written.

    Args:
        file:       An open, writable text file handle.
        connection: An active SQLAlchemy connection.
        table:      Name of the source table to export.
    """
    print(f"    Processing table: {table}")

    # --- DDL ---
    row = connection.execute(text(f"SHOW CREATE TABLE `{table}`")).fetchone()
    file.write(f"{row[1]};\n\n")

    # --- Data ---
    result = connection.execute(text(f"SELECT * FROM `{table}`"))
    columns = result.keys()
    rows    = result.fetchall()

    if not rows:
        return

    col_list = ", ".join(f"`{col}`" for col in columns)
    file.write(f"INSERT INTO `{table}` ({col_list}) VALUES\n")

    value_rows = [
        "(" + ", ".join(format_sql_value(val) for val in row) + ")"
        for row in rows
    ]
    file.write(",\n".join(value_rows) + ";\n\n")


def export_database(
    connection,
    output_dir: Path,
    db_name: str,
    tables: list[str]
) -> None:
    db_dir = output_dir / db_name
    db_dir.mkdir(parents=True, exist_ok=True)
    sql_path = db_dir / "init.sql"

    print(f"Generating {sql_path} ...")

    with sql_path.open("w", encoding="utf-8") as f:
        f.write(f"CREATE DATABASE IF NOT EXISTS `{db_name}`;\n")
        f.write(f"USE `{db_name}`;\n")
        
        # Tell MySQL to temporarily ignore foreign keys while building this DB
        f.write("SET FOREIGN_KEY_CHECKS = 0;\n\n")

        for table in tables:
            write_table(f, connection, table)

        # Turn foreign keys back on when finished
        f.write("SET FOREIGN_KEY_CHECKS = 1;\n")

    print(f"  Done → {sql_path}\n")
# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Export all databases defined in :data:`DB_BLUEPRINTS` to SQL scripts."""
    output_dir = ensure_directory(OUTPUT_DIR)
    engine     = create_engine(SRC_URL)

    with engine.connect() as connection:
        for db_name, tables in DB_BLUEPRINTS.items():
            export_database(connection, output_dir, db_name, tables)

    print("Export complete.")


if __name__ == "__main__":
    main()