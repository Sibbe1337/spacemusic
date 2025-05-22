from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# This block is to ensure that the models can be found by Alembic
import os
import sys
from pathlib import Path

# Add project root to sys.path to allow absolute-like imports for services
# Assuming this env.py is in services/payouts/migrations/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent # Adjust if structure differs
sys.path.append(str(PROJECT_ROOT))

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
from services.payouts.models import SQLModel  # Import SQLModel from your models file
target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

PAYOUTS_DB_ENV_VAR = "PAYOUTS_DB_CONNECTION_STRING"

def get_url():
    # Prioritize environment variable, fall back to alembic.ini if not set (though ini is now a placeholder)
    db_url = os.getenv(PAYOUTS_DB_ENV_VAR)
    if db_url:
        return db_url
    # Fallback to the URL in alembic.ini (which is a placeholder)
    # This path should ideally not be taken if PAYOUTS_DB_ENV_VAR is always set when running alembic.
    return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Use the get_url() function to ensure PAYOUTS_DB_CONNECTION_STRING is used
    configuration = config.get_section(config.config_ini_section, {})
    db_url_for_online = get_url()
    if not db_url_for_online:
        raise ValueError(f"Database URL not configured. Set {PAYOUTS_DB_ENV_VAR} or sqlalchemy.url in alembic.ini")
    configuration["sqlalchemy.url"] = db_url_for_online

    connectable = engine_from_config(
        configuration, # Use the modified configuration
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
