import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db.base_class import Base

from app.models import all_models  # noqa: F401

config = context.config

# Skip fileConfig to avoid logging configuration issues
# if config.config_file_name is not None:
#     fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def get_url() -> str:
    # Try environment variables first (from docker-compose)
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    url = os.getenv("ALEMBIC_DATABASE_URL")
    if url:
        return url
    # Fallback to alembic.ini config
    return config.get_main_option("sqlalchemy.url") or "postgresql://postgres:postgres@db:5432/aiseek"


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section)
    if configuration is None:
        configuration = {}
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
