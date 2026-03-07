import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
_DEFAULT_SQLITE_PATH = os.path.join(_REPO_ROOT, "sql_app.db")
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_DEFAULT_SQLITE_PATH}")
SQLALCHEMY_READ_DATABASE_URL = os.getenv("READ_DATABASE_URL") or SQLALCHEMY_DATABASE_URL


def _int_env(name: str, default: int) -> int:
    try:
        v = int(str(os.getenv(name, "")).strip())
        return v if v > 0 else default
    except Exception:
        return default


def _int_env_range(name: str, default: int, low: int, high: int) -> int:
    v = _int_env(name, default)
    if v < int(low):
        return int(low)
    if v > int(high):
        return int(high)
    return int(v)


def _make_engine(url: str):
    if "sqlite" in url:
        eng = create_engine(url, connect_args={"check_same_thread": False})
        try:
            @event.listens_for(eng, "connect")
            def _sqlite_on_connect(dbapi_connection, connection_record):
                cur = dbapi_connection.cursor()
                try:
                    cur.execute("PRAGMA journal_mode=WAL;")
                    cur.execute("PRAGMA synchronous=NORMAL;")
                    cur.execute("PRAGMA temp_store=MEMORY;")
                    cur.execute("PRAGMA busy_timeout=5000;")
                finally:
                    cur.close()
        except Exception:
            pass
        return eng

    pool_size = _int_env_range("DB_POOL_SIZE", 30, 5, 300)
    max_overflow = _int_env_range("DB_MAX_OVERFLOW", 60, 0, 600)
    pool_timeout = _int_env_range("DB_POOL_TIMEOUT_SEC", 15, 1, 120)
    pool_recycle = _int_env_range("DB_POOL_RECYCLE_SEC", 1800, 60, 7200)
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
        pool_use_lifo=True,
    )


engine = _make_engine(SQLALCHEMY_DATABASE_URL)
engine_read = engine if SQLALCHEMY_READ_DATABASE_URL == SQLALCHEMY_DATABASE_URL else _make_engine(SQLALCHEMY_READ_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
SessionLocalRead = sessionmaker(autocommit=False, autoflush=False, bind=engine_read)
