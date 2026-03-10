import os
import sqlite3
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
    command.upgrade(cfg, "head")
