import pytest
import pytest_asyncio

from riverorm import Model, constants
from riverorm.config import config
from riverorm.db import DatabaseRegistry, MySQLDatabase, PostgresDatabase
from tests.models import Order, Product, User


@pytest.fixture(scope="session", params=[constants.POSTGRES])  # TODO: Add constants.MYSQL
def db_type(request: pytest.FixtureRequest) -> str:
    return str(request.param)


@pytest.fixture(scope="session", autouse=True)
def setup_db_registry(db_type: str):
    # Register both Postgres and MySQL connections for tests
    DatabaseRegistry.clear()
    DatabaseRegistry.register("postgres", PostgresDatabase(config.POSTGRES_DSN, config.DEBUG))
    DatabaseRegistry.register("mysql", MySQLDatabase(config.MYSQL_DSN, config.DEBUG))
    DatabaseRegistry.set_default(db_type)


@pytest.fixture
def db_models() -> list[type[Model]]:
    return [Order, Product, User]


@pytest_asyncio.fixture(scope="function")
async def db_setup_and_teardown(db_models: list[type[Model]]):
    # Connect all registered DBs
    await DatabaseRegistry.connect()
    # Drop all tables to ensure a clean state
    for model in db_models:
        await model.drop_table()
    # Recreate tables
    for model in db_models:
        await model.create_table()
    yield
    # Teardown: close all DB connections
    await DatabaseRegistry.close()
