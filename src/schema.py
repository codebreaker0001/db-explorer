"""
Schema Inspector
================
This file knows how to look INSIDE your database and describe its structure.

Think of a database like a filing cabinet:
- The "schema" is the cabinet itself (the overall structure)
- "Tables" are the drawers (each holds a specific type of data)
- "Columns" are the labels on folders inside each drawer
  (name, type, whether it can be empty, etc.)

This inspector opens the cabinet and reads all the labels for you.
"""

import logging

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


class SchemaInspector:
    """
    Inspects database structure — tables, columns, types, keys.

    Usage:
        inspector = SchemaInspector(engine)
        tables = await inspector.list_tables()
        details = await inspector.describe_table("users")
    """

    def __init__(self, engine: AsyncEngine):
        self._engine = engine

    async def list_tables(self, schema: str | None = None) -> list[dict]:
        """
        List all tables in the database.

        Returns a list like:
        [
            {"name": "users", "schema": "public", "row_count": 1500},
            {"name": "orders", "schema": "public", "row_count": 3200},
        ]

        The row_count is approximate — it's fast but not perfectly exact.
        For exact counts, you'd run SELECT COUNT(*), which can be slow
        on huge tables.
        """
        tables = []

        # run_sync lets us use SQLAlchemy's synchronous inspector
        # inside our async code. Think of it as a bridge between
        # the two styles.
        async with self._engine.connect() as conn:
            # Get list of table names
            table_names = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names(schema=schema)
            )

            # For each table, get an approximate row count
            for table_name in table_names:
                try:
                    # This is a quick way to count rows
                    # We use a simple SELECT COUNT(*) since for Phase 1
                    # we're working with small databases
                    result = await conn.execute(
                        text(f'SELECT COUNT(*) FROM "{table_name}"')
                    )
                    row_count = result.scalar() or 0
                except Exception:
                    row_count = -1  # -1 means "couldn't count"

                tables.append({
                    "name": table_name,
                    "schema": schema or "default",
                    "row_count": row_count,
                })

        return tables

    async def describe_table(self, table_name: str, schema: str | None = None) -> dict:
        """
        Describe a table's structure in detail.

        Returns something like:
        {
            "name": "users",
            "columns": [
                {
                    "name": "id",
                    "type": "INTEGER",
                    "nullable": False,       # Can this column be empty?
                    "default": None,         # Default value if not provided
                    "primary_key": True,     # Is this the unique identifier?
                },
                {
                    "name": "email",
                    "type": "VARCHAR(255)",
                    "nullable": False,
                    "default": None,
                    "primary_key": False,
                },
            ],
            "primary_keys": ["id"],
            "row_count": 1500,
        }
        """
        async with self._engine.connect() as conn:
            # Get column information
            columns_info = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_columns(
                    table_name, schema=schema
                )
            )

            # Get primary key columns
            pk_info = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_pk_constraint(
                    table_name, schema=schema
                )
            )

            pk_columns = pk_info.get("constrained_columns", [])

            # Build column details
            columns = []
            for col in columns_info:
                columns.append({
                    "name": col["name"],
                    "type": str(col["type"]),        # e.g., "INTEGER", "VARCHAR(255)"
                    "nullable": col.get("nullable", True),
                    "default": str(col["default"]) if col.get("default") is not None else None,
                    "primary_key": col["name"] in pk_columns,
                })

            # Get row count
            try:
                result = await conn.execute(
                    text(f'SELECT COUNT(*) FROM "{table_name}"')
                )
                row_count = result.scalar() or 0
            except Exception:
                row_count = -1

            return {
                "name": table_name,
                "columns": columns,
                "primary_keys": pk_columns,
                "row_count": row_count,
            }

    async def get_foreign_keys(self, table_name: str, schema: str | None = None) -> list[dict]:
        """
        Get foreign key relationships for a table.

        Foreign keys are like cross-references between tables.
        If the "orders" table has a "user_id" column that points to
        the "users" table, that's a foreign key — it links orders to users.

        Returns:
        [
            {
                "column": "user_id",
                "references_table": "users",
                "references_column": "id",
            }
        ]
        """
        async with self._engine.connect() as conn:
            fk_info = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_foreign_keys(
                    table_name, schema=schema
                )
            )

            foreign_keys = []
            for fk in fk_info:
                for i, col in enumerate(fk.get("constrained_columns", [])):
                    ref_cols = fk.get("referred_columns", [])
                    foreign_keys.append({
                        "column": col,
                        "references_table": fk.get("referred_table", "unknown"),
                        "references_column": ref_cols[i] if i < len(ref_cols) else "unknown",
                    })

            return foreign_keys