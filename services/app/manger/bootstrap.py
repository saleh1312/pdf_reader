from sqlalchemy import Engine

from manger.infra.db.mapper import init_db, start_mappers
from manger.infra.db.uow import DEFAULT_ENGINE


def bootstrap(engine: Engine = DEFAULT_ENGINE) -> None:
    """Prepare the app to use the database: map the domain and create tables."""
    start_mappers()
    init_db(engine)
