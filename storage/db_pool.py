import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from core.config import settings
import sys

try:
    # Maintains a thread-safe pool of up to 20 concurrent connections
    db_pool = ThreadedConnectionPool(
        minconn=1,
        maxconn=20,
        dsn=settings.SQLALCHEMY_DATABASE_URI
    )
    print("[DATABASE POOL] Threaded connection pool initialized successfully.")
except Exception as e:
    print(f"[DATABASE ERROR] Failed to initialize connection pool: {e}")
    sys.exit(1)