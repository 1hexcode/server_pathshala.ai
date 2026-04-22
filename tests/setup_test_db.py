import asyncio
import asyncpg
import os
from alembic.config import Config
from alembic import command
from urllib.parse import urlparse

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/patshala"
)

# Parse to isolate host, port, user, pass
# expected something like postgresql+asyncpg://postgres:postgres@localhost:5432/patshala
parsed = urlparse(DATABASE_URL.replace("postgresql+asyncpg", "postgresql"))

DB_USER = parsed.username or "postgres"
DB_PASS = parsed.password or "postgres"
DB_HOST = parsed.hostname or "localhost"
DB_PORT = parsed.port or 5432
TEST_DB_NAME = "patshala_test"

# The master pg connection string
MASTER_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/postgres"
TEST_URL_ALEMBIC = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{TEST_DB_NAME}"


async def setup_db():
    print(f"Connecting to master db at {MASTER_URL} to setup {TEST_DB_NAME}...")
    try:
        conn = await asyncpg.connect(MASTER_URL)
        
        # Terminate any existing connections to the test DB
        await conn.execute(f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{TEST_DB_NAME}'
              AND pid <> pg_backend_pid();
        """)
        
        # Drop and create
        await conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}")
        await conn.execute(f"CREATE DATABASE {TEST_DB_NAME}")
        print(f"Database {TEST_DB_NAME} created.")
        
        await conn.close()
    except Exception as e:
        print(f"Error recreating database: {e}")
        return

    # Now run migrations on the new test db
    print("Running initial alembic migrations on test db...")
    
    # We need to temporarily override the alembic.ini or env.py url, 
    # but Alembic can be configured via x args or altering the URL programmatically.
    alembic_cfg = Config("alembic.ini")
    os.environ["DATABASE_URL"] = TEST_URL_ALEMBIC
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_URL_ALEMBIC)
    
    command.upgrade(alembic_cfg, "head")
    print("Database testing environment successfully built!")

if __name__ == "__main__":
    asyncio.run(setup_db())
