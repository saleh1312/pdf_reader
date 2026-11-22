import pytest

from manger.bootstrap import bootstrap
from manger.infra.db.mapper import clear_db
from manger.infra.db.uow import DEFAULT_ENGINE, FakeUnitOfWork, SqlAlchemyUnitOfWork
from manger.services.unit_of_work import AbstractUnitOfWork


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--real",
        action="store_true",
        help="run service tests against Postgres with SqlAlchemyUnitOfWork",
    )
    parser.addoption(
        "--clean",
        action="store_true",
        help="with --real, delete all rows (keeping the schema) after the run",
    )


def pytest_configure(config: pytest.Config) -> None:
    if config.getoption("--clean") and not config.getoption("--real"):
        raise pytest.UsageError("--clean only makes sense together with --real")


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
