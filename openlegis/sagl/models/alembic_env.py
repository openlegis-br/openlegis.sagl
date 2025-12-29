# -*- coding: utf-8 -*-
"""
Alembic environment configuration for SAGL migrations
"""
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# Import the Base and all models
from openlegis.sagl.models.models import Base
# Import all models to ensure they're registered with Base
import openlegis.sagl.models.models  # noqa

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Get the database URL from z3c.saconfig or environment
def get_database_url():
    """Get database URL from z3c.saconfig or environment variables"""
    import os
    
    # Try to get from environment first
    mysql_host = os.environ.get('MYSQL_HOST', '127.0.0.1')
    mysql_user = os.environ.get('MYSQL_USER', 'root')
    mysql_pass = os.environ.get('MYSQL_PASS', 'openlegis')
    mysql_db = os.environ.get('MYSQL_DB', 'openlegis')
    
    # Use pymysql driver (already in buildout)
    database_url = f"mysql+pymysql://{mysql_user}:{mysql_pass}@{mysql_host}/{mysql_db}?charset=utf8mb4"
    
    return database_url

# Set the database URL in config
config.set_main_option('sqlalchemy.url', get_database_url())

# add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
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
    """Run migrations in 'online' mode."""
    # For migrations, use NullPool to avoid connection pool issues
    # But still configure pool_pre_ping if we switch to QueuePool in the future
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        # Add pool_pre_ping even with NullPool for safety (though it won't be used)
        # This is a no-op with NullPool but keeps the code consistent
    )

    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection, 
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=False,  # Ignora diferenças em server_default para evitar migrations desnecessárias
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        # Garante que a conexão seja fechada
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

