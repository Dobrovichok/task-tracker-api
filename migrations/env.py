from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, create_engine, pool

from app.config import DatabaseSettings
from app.models import Base


config = context.config
if config.config_file_name and config.attributes.get("connection") is None:
    fileConfig(config.config_file_name)


def run_online(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata, compare_server_default=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(url=DatabaseSettings().url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    supplied_connection = config.attributes.get("connection")
    if supplied_connection is not None:
        run_online(supplied_connection)
    else:
        engine = create_engine(DatabaseSettings().url, poolclass=pool.NullPool)
        with engine.connect() as connection:
            run_online(connection)
