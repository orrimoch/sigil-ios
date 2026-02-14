"""
Sigil Auth — Database setup with SQLAlchemy async (REC-272).

Supports both SQLite and PostgreSQL based on environment configuration:
- SQLite: Default for local development
- PostgreSQL: For production (Railway, etc.)

Environment Variables:
- DATABASE_URL: Full database URL (postgres://... or sqlite+aiosqlite:///...)
- DATABASE_TYPE: "sqlite" or "postgresql" (overridden by DATABASE_URL if set)
"""

import os
from pathlib import Path
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
import logging

logger = logging.getLogger(__name__)


def get_database_url() -> str:
    """
    Determine the database URL based on environment configuration.
    
    Priority:
    1. DATABASE_URL environment variable (production)
    2. DATABASE_TYPE + local SQLite path (development)
    
    Returns:
        Async-compatible database URL
    """
    # Check for explicit DATABASE_URL (Railway/production)
    database_url = os.environ.get("DATABASE_URL")
    
    if database_url:
        # Convert postgres:// to postgresql+asyncpg:// for async support
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
        logger.info(f"Using PostgreSQL database from DATABASE_URL")
        return database_url
    
    # Check DATABASE_TYPE for explicit selection
    db_type = os.environ.get("DATABASE_TYPE", "sqlite").lower()
    
    if db_type == "postgresql":
        # Build PostgreSQL URL from components
        pg_host = os.environ.get("PGHOST", "localhost")
        pg_port = os.environ.get("PGPORT", "5432")
        pg_user = os.environ.get("PGUSER", "postgres")
        pg_pass = os.environ.get("PGPASSWORD", "")
        pg_db = os.environ.get("PGDATABASE", "sigil")
        
        url = f"postgresql+asyncpg://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
        logger.info(f"Using PostgreSQL database: {pg_host}:{pg_port}/{pg_db}")
        return url
    
    # Default: SQLite for local development
    data_dir = Path(__file__).parent.parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "sigil.db"
    
    url = f"sqlite+aiosqlite:///{db_path}"
    logger.info(f"Using SQLite database: {db_path}")
    return url


def get_engine_options() -> dict:
    """
    Get SQLAlchemy engine options based on database type.
    
    Returns:
        Dict of engine configuration options
    """
    database_url = get_database_url()
    
    if "postgresql" in database_url:
        return {
            "echo": os.environ.get("SQL_ECHO", "false").lower() == "true",
            "pool_size": int(os.environ.get("DB_POOL_SIZE", "5")),
            "max_overflow": int(os.environ.get("DB_MAX_OVERFLOW", "10")),
            "pool_timeout": int(os.environ.get("DB_POOL_TIMEOUT", "30")),
            "pool_recycle": int(os.environ.get("DB_POOL_RECYCLE", "1800")),
        }
    else:
        # SQLite options
        return {
            "echo": os.environ.get("SQL_ECHO", "false").lower() == "true",
        }


# Database configuration
DATABASE_URL = get_database_url()

# Create engine with appropriate options
engine = create_async_engine(DATABASE_URL, **get_engine_options())

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Create all tables if they don't exist."""
    from .models import User  # noqa: F401 — ensure model is registered
    from db.models import UserPortfolio, UserPosition, UserOrder  # noqa: F401
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info(f"Database initialized: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")


async def get_db_session() -> AsyncSession:
    """FastAPI dependency — yields an async session."""
    async with async_session_factory() as session:
        yield session


def get_database_info() -> dict:
    """
    Get information about the current database configuration.
    
    Returns:
        Dict with database type, connection info (sanitized)
    """
    url = DATABASE_URL
    
    # Sanitize URL for display (remove password)
    if "@" in url:
        parts = url.split("@")
        # Remove password from first part
        creds_part = parts[0].rsplit(":", 1)[0]  # Remove password
        display_url = f"{creds_part}:***@{parts[1]}"
    else:
        display_url = url
    
    return {
        "type": "postgresql" if "postgresql" in url else "sqlite",
        "url": display_url,
        "pool_size": get_engine_options().get("pool_size", "N/A"),
    }


# Legacy compatibility - keep DB_PATH for backward compatibility with existing code
DATA_DIR = Path(__file__).parent.parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "sigil.db"
