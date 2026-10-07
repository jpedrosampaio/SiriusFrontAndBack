from logging.config import fileConfig
from alembic import context
from sqlalchemy import create_engine, pool
from db.engine import database_url
from db.base import Base
import db.models  # noqa: F401

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)


def migrate(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(url=database_url(direct=True), target_metadata=Base.metadata,
                      literal_binds=True, dialect_opts={'paramstyle': 'named'})
    with context.begin_transaction():
        context.run_migrations()
else:
    # Psycopg also supports synchronous connections. The migration CLI does not
    # share the runtime pool and works on Windows without an asyncio policy.
    engine = create_engine(database_url(direct=True), poolclass=pool.NullPool,
                           echo=False, hide_parameters=True, connect_args={'connect_timeout': 15})
    with engine.connect() as connection:
        migrate(connection)
    engine.dispose()
