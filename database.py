import asyncpg
import os
from contextlib import asynccontextmanager

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:fncjjcnf@localhost:5444/boat_station_db",
)

# Для psycopg2 (синхронный)
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


# Менеджер контекста для синхронного psycopg2
from contextlib import contextmanager

@contextmanager
def db_query():
    conn = get_db_connection()
    try:
        yield conn.cursor()
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
