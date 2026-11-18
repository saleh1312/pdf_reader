import pytest


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
