import os
import sqlite3
import time
from pathlib import Path


def run_migrations() -> None:
    try:
        from app.core.config import settings

        if not bool(getattr(settings, "AUTO_MIGRATE", True)):
            return
    except Exception:
        if os.getenv("AUTO_MIGRATE", "1") not in {"1", "true", "TRUE", "yes", "YES"}:
            return
    try:
        from alembic import command
        from alembic.config import Config
    except Exception:
        return

    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("prepend_sys_path", str(root))
    
    # Retry logic for migrations (e.g. waiting for DB ready)
    max_retries = 3
    for i in range(max_retries):
        try:
            command.upgrade(cfg, "head")
            return
        except Exception as e:
            if i == max_retries - 1:
                print(f"Migration failed after {max_retries} attempts: {e}")
                # We don't raise here to avoid crashing the app completely, 
                # but DB operations might fail later.
                raise e
            print(f"Migration attempt {i+1} failed: {e}. Retrying in 2s...")
            time.sleep(2)
