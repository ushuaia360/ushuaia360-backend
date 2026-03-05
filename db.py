"""
Database connection setup with asyncpg
"""
import os
import asyncpg
from urllib.parse import urlparse
from quart import current_app
from contextlib import asynccontextmanager

db_pool = None


def _is_pooler(dsn: str) -> bool:
    """Check if DSN is a pooler connection"""
    host = urlparse(dsn).hostname or ""
    return "pooler.supabase.com" in host


async def init_db():
    """Initialize database connection pool"""
    global db_pool
    dsn = current_app.config.get("DATABASE_URL")
    if not dsn:
        raise ValueError("DATABASE_URL must be set in configuration")
    
    db_pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=int(os.getenv("DB_POOL_MIN", "1")),
        max_size=int(os.getenv("DB_POOL_MAX", "8")),
        command_timeout=30,
        max_inactive_connection_lifetime=300,
        statement_cache_size=0 if _is_pooler(dsn) else 1000,
        server_settings={"application_name": "ushuaia360-backend"},
    )
    # Test connection
    async with db_pool.acquire() as conn:
        await conn.execute("SELECT 1")


@asynccontextmanager
async def get_conn():
    """Get a database connection from the pool"""
    conn = await db_pool.acquire()
    try:
        yield conn
    finally:
        await db_pool.release(conn)
