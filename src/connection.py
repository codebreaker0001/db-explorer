"""
Connection Manager
==================
This file handles connecting to your database.

Think of it like a phone operator — it knows how to dial different databases
(SQLite, PostgreSQL, MySQL) and keeps the line open so we can make queries.

KEY CONCEPTS:
- "Engine" = the connection to your database (like plugging in a cable)
- "Session" = a conversation with the database (ask questions, get answers)
- "Async" = non-blocking (the server can handle other requests while waiting
  for the database to respond)
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages the database connection.

    Usage:
        manager = ConnectionManager()
        engine = await manager.connect()          # connect using .env file
        engine = await manager.connect(url="...")  # connect using explicit URL
    """

    def __init__(self):
        self._engine: AsyncEngine | None = None
        self._db_type: str = "unknown"

    @property
    def engine(self) -> AsyncEngine:
        """Get the current database engine. Raises if not connected."""
        if self._engine is None:
            raise RuntimeError("Not connected to any database. Call connect() first.")
        return self._engine

    @property
    def db_type(self) -> str:
        """Returns the type of database we're connected to: 'sqlite', 'postgresql', or 'mysql'."""
        return self._db_type

    def _make_async_url(self, url: str) -> str:
        """
        Convert a regular database URL to an async-compatible one.

        Regular URLs look like:     sqlite:///mydb.db
        Async URLs look like:       sqlite+aiosqlite:///mydb.db

        SQLAlchemy needs the async version to work with our async server.
        """
        if url.startswith("sqlite://"):
            self._db_type = "sqlite"
            return url.replace("sqlite://", "sqlite+aiosqlite://", 1)

        elif url.startswith(("postgresql://", "postgres://")):
            self._db_type = "postgresql"
            # postgres:// is a common alias (Heroku, Railway, etc.)
            if url.startswith("postgres://"):
                url = "postgresql://" + url[len("postgres://"):]
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)

        elif url.startswith("mysql://"):
            self._db_type = "mysql"
            return url.replace("mysql://", "mysql+aiomysql://", 1)

        else:
            # Already has an async driver specified, or unknown format
            # Try to detect the type from the URL
            if "sqlite" in url:
                self._db_type = "sqlite"
            elif "postgresql" in url or "postgres" in url:
                self._db_type = "postgresql"
            elif "mysql" in url:
                self._db_type = "mysql"
            return url

    async def connect(self, url: str | None = None) -> AsyncEngine:
        """
        Connect to a database.

        Args:
            url: Database URL. If not provided, reads from DATABASE_URL
                 in your .env file.

        Returns:
            The SQLAlchemy async engine (our connection to the database).

        Examples:
            SQLite:     sqlite:///./my_database.db
            PostgreSQL: postgresql://user:password@localhost:5432/mydb
            MySQL:      mysql://user:password@localhost:3306/mydb
        """
        # If no URL provided, try to load from .env file
        if url is None:
            load_dotenv()  # Reads .env file in current directory
            url = os.getenv("DATABASE_URL")
            if url is None:
                raise ValueError(
                    "No database URL provided. Either pass one to connect() "
                    "or set DATABASE_URL in your .env file."
                )

        # Convert to async URL
        async_url = self._make_async_url(url)

        # Close existing connection if any
        if self._engine is not None:
            await self._engine.dispose()

        # Create the engine
        _driver_install_hints = {
            "postgresql": "pip install asyncpg",
            "mysql": "pip install aiomysql",
        }
        try:
            self._engine = create_async_engine(
                async_url,
                echo=False,
                pool_pre_ping=True,
            )
        except Exception as e:
            hint = _driver_install_hints.get(self._db_type)
            if hint and "no module" in str(e).lower():
                raise RuntimeError(
                    f"Async driver not installed for {self._db_type}. "
                    f"Run: {hint}"
                ) from e
            raise

        logger.info(f"Connected to {self._db_type} database")
        return self._engine

    async def disconnect(self):
        """Close the database connection cleanly."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            logger.info("Disconnected from database")

    async def test_connection(self) -> bool:
        """
        Test if the database connection is working.

        Returns True if we can talk to the database, False otherwise.
        """
        try:
            from sqlalchemy import text

            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False