import pytest

from manger.bootstrap import bootstrap
from manger.infra.db.mapper import clear_db
from manger.infra.db.uow import (
    DEFAULT_ENGINE,
    AbstractUnitOfWork,
    FakeUnitOfWork,
    SqlAlchemyUnitOfWork,
)


@pytest.fixture(scope="session")
def database(request: pytest.FixtureRequest):
    bootstrap()
    yield
    if request.config.getoption("--clean"):
        clear_db(DEFAULT_ENGINE)


@pytest.fixture
def uow(request: pytest.FixtureRequest) -> AbstractUnitOfWork:
    """SqlAlchemyUnitOfWork with `--real`, otherwise the in-memory fake."""
    if request.config.getoption("--real"):
        request.getfixturevalue("database")
        return SqlAlchemyUnitOfWork()
    return FakeUnitOfWork()
