"""
models.py
=========
SQLAlchemy ORM models for the central catalog database: tracks which
containers were scanned, what tables they have, and each table's columns.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, String, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class CatalogContainer(Base):
    """Tracks the different source Docker containers."""
    __tablename__ = "catalog_containers"

    id: Mapped[int] = mapped_column(primary_key=True)
    container_name: Mapped[str] = mapped_column(String(100), unique=True)
    last_scanned_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    tables = relationship("CatalogTable", back_populates="container", cascade="all, delete-orphan")


class CatalogTable(Base):
    """Tracks the tables discovered inside each container."""
    __tablename__ = "catalog_tables"

    id: Mapped[int] = mapped_column(primary_key=True)
    container_id: Mapped[int] = mapped_column(ForeignKey("catalog_containers.id"))
    table_name: Mapped[str] = mapped_column(String(100))

    container = relationship("CatalogContainer", back_populates="tables")
    columns = relationship("CatalogColumn", back_populates="table", cascade="all, delete-orphan")


class CatalogColumn(Base):
    """Tracks the fine-grained column details for every table."""
    __tablename__ = "catalog_columns"

    id: Mapped[int] = mapped_column(primary_key=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("catalog_tables.id"))
    column_name: Mapped[str] = mapped_column(String(100))
    data_type: Mapped[str] = mapped_column(String(100))
    is_nullable: Mapped[bool] = mapped_column(Boolean)
    is_primary_key: Mapped[bool] = mapped_column(Boolean)

    table = relationship("CatalogTable", back_populates="columns")


def create_catalog_schema(catalog_engine) -> None:
    """Create the catalog tables (containers/tables/columns) if they don't exist."""
    Base.metadata.create_all(bind=catalog_engine)
    print("✓ Catalog tracking architecture successfully initialized.")