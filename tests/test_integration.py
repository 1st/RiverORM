import pytest

from tests.models import User


@pytest.mark.asyncio
async def test_create_and_fetch_user(db_setup_and_teardown):
    user = User(username="Alice", email="alice@example.com", is_active=True)
    await user.save()

    all_users = await User.all()
    assert len(all_users) == 1

    fetched = await User.get(username="Alice")
    assert fetched is not None
    assert fetched.id is not None  # Auto-increment PK should be set
    assert fetched.username == "Alice"
    assert fetched.email == "alice@example.com"
    assert fetched.is_active is True
