import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

if context.config.config_file_name:
    fileConfig(context.config.config_file_name)

# Migrations are hand-written SQL; no ORM metadata / autogenerate.
engine = create_engine(os.environ["DATABASE_URL"])
with engine.connect() as connection:
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()
