import os
import socket
from logging.config import fileConfig

from sqlalchemy import engine_from_config, event, pool

from alembic import context

from app.models import Base  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))

# Tolère les tabulations/espaces/guillemets ajoutés par un copier-coller.
if database_url:
    database_url = database_url.strip().strip('"').strip("'").strip()

if database_url:
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql+psycopg://"):
        pass
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)

config.set_main_option("sqlalchemy.url", database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"connect_timeout": 30},
    )

    # Force IPv4 (Railway a l'IPv6 sortant cassé — voir app/db.py)
    @event.listens_for(connectable, "do_connect")
    def _force_ipv4(dialect, conn_rec, cargs, cparams):
        host = cparams.get("host")
        if host and "neon.tech" in host:
            try:
                infos = socket.getaddrinfo(
                    host, cparams.get("port", 5432), socket.AF_INET, socket.SOCK_STREAM
                )
                if infos:
                    cparams["hostaddr"] = infos[0][4][0]
            except OSError:
                pass

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
