import pytest
import pytest_asyncio

from riverorm import Model, constants
from riverorm.config import config
from riverorm.db import BaseDatabase, get_database
from tests.models import Order, Product, User


@pytest.fixture(params=[constants.POSTGRES])  # TODO: Add constants.MYSQL
def db(request: pytest.FixtureRequest) -> BaseDatabase:
    return get_database(request.param, debug=config.DEBUG)


@pytest.fixture
def db_models() -> list[type[Model]]:
    """Return all model classes used in tests."""
    return [Order, Product, User]


@pytest_asyncio.fixture(scope="function")
async def db_setup_and_teardown(db: BaseDatabase, db_models: list[type[Model]]):
    await db.connect()
    # Drop all tables to ensure a clean state
    for model in db_models:
        await model.drop_table()
    # Recreate tables
    for model in db_models:
        await model.create_table()
    # Pass control to the test
    yield
    # Teardown: close the database connection
    await db.close()
