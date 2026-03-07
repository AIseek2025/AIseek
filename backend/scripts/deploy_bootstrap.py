import argparse
import os
from pathlib import Path


def _truthy(v: str) -> bool:
    return str(v or "").strip() in {"1", "true", "TRUE", "yes", "YES"}


def run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", "backend/alembic")
    cfg.set_main_option("prepend_sys_path", "backend")
    command.upgrade(cfg, "head")


def run_es_bootstrap(reindex: bool, limit: int) -> None:
    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.services.search_service import ensure_posts_alias, rebuild_posts_index

    s = get_settings()
    if not s.ELASTICSEARCH_URL or not s.ELASTICSEARCH_INDEX:
        return

    ok = ensure_posts_alias(s.ELASTICSEARCH_URL, s.ELASTICSEARCH_INDEX)
    if not ok:
        raise SystemExit("ensure_posts_alias_failed")
    if not reindex:
        return

    db = SessionLocal()
    try:
        out = rebuild_posts_index(db, limit=int(limit or 5000))
    finally:
        try:
            db.close()
        except Exception:
            pass
    if not int(out.get("ok") or 0):
        raise SystemExit("reindex_failed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--migrate", action="store_true", default=_truthy(os.getenv("AUTO_MIGRATE", "1")))
    ap.add_argument("--no-migrate", action="store_true", default=False)
    ap.add_argument("--es", action="store_true", default=False, help="启用 ES alias/可选重建")
    ap.add_argument("--reindex", action="store_true", default=False, help="执行 ES 重建（需要 --es）")
    ap.add_argument("--reindex-limit", type=int, default=5000)
    args = ap.parse_args()

    do_migrate = bool(args.migrate) and not bool(args.no_migrate)
    if do_migrate:
        run_migrations()

    if args.es:
        run_es_bootstrap(bool(args.reindex), int(args.reindex_limit or 5000))

    print("ok")


if __name__ == "__main__":
    main()

