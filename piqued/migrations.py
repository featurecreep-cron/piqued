"""Lightweight schema migrations.

Until we adopt Alembic, this module performs idempotent ALTER TABLE statements
on startup to bring existing databases up to the current model schema.

Each migration is a (table, column, ddl) tuple. The runner checks PRAGMA
table_info to see if the column already exists before issuing the ALTER.
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

logger = logging.getLogger(__name__)

# (table, column, full ALTER TABLE DDL)
# When you add a new column to a model, add an entry here too.
COLUMN_ADDITIONS: list[tuple[str, str, str]] = [
    (
        "users",
        "preferences",
        "ALTER TABLE users ADD COLUMN preferences TEXT NOT NULL DEFAULT '{}'",
    ),
]


async def run_migrations(conn: AsyncConnection) -> None:
    """Apply any pending column additions to existing tables."""
    for table, column, ddl in COLUMN_ADDITIONS:
        result = await conn.execute(text(f"PRAGMA table_info({table})"))
        existing_columns = {row[1] for row in result.fetchall()}
        if column in existing_columns:
            continue
        logger.warning("Migrating: adding %s.%s", table, column)
        await conn.execute(text(ddl))
