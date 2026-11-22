from sqlalchemy import Engine

from manger.infra.db.session.mapper import init_db, start_mappers
from manger.infra.db.session.uow import CHATBOT_ENGINE


def bootstrap(engine: Engine = CHATBOT_ENGINE) -> None:
    """Prepare the chatbot to use its database: map the domain and create tables."""
    start_mappers()
    init_db(engine)
