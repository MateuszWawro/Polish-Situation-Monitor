import os
from functools import cache

from sqlalchemy import Engine, create_engine


@cache
def get_engine() -> Engine:
    return create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
