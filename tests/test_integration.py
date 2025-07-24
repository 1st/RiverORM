import os

import pytest
import pytest_asyncio

from riverorm.db import db
from tests.models import User

POSTGRES_DSN = os.getenv(
    "POSTGRES_DSN", "postgresql://river_user:river_pass@localhost:5432/river_test"
)
MYSQL_DSN = os.getenv("MYSQL_DSN", "mysql://river_user:river_pass@localhost:3306/river_test")


@pytest_asyncio.fixture(scope="function")
async def db_setup_and_teardown():
    await db.connect(POSTGRES_DSN)
    await User.drop_table()
    await User.create_table()
    yield
    await db.close()


@pytest.mark.asyncio
async def test_create_and_fetch_user(db_setup_and_teardown):
    user = User(username="Alice", email="alice@example.com", is_active=True)
    await user.save()

    all_users = await User.all()
    assert len(all_users) == 1

    fetched = await User.get(username="Alice")
    assert fetched is not None
    assert fetched.id is None  # TODO: Add auto-increment support
    assert fetched.username == "Alice"
    assert fetched.email == "alice@example.com"
    assert fetched.is_active is True
