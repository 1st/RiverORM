import pytest
import pytest_asyncio

from riverorm.config import config
from riverorm.db import db
from tests.models import User


@pytest_asyncio.fixture(scope="function")
async def db_setup_and_teardown():
    await db.connect(config.POSTGRES_DSN)
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
