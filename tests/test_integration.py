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


@pytest.mark.asyncio
async def test_save_update_path(db_setup_and_teardown):
    user = User(username="bob", email="bob@ex.com", is_active=True)
    await user.save()
    original_id = user.id

    user.email = "bob2@ex.com"
    user.is_active = False
    await user.save()

    fetched = await User.objects.get(id=original_id)
    assert fetched.email == "bob2@ex.com"
    assert fetched.is_active is False
    assert await User.objects.count() == 1  # no duplicate row created


@pytest.mark.asyncio
async def test_instance_delete(db_setup_and_teardown):
    user = User(username="carol", email="carol@ex.com", is_active=True)
    await user.save()
    assert await User.objects.count() == 1

    await user.delete()

    assert await User.objects.count() == 0
    assert await User.objects.filter(username="carol").exists() is False


@pytest.mark.asyncio
async def test_instance_delete_leaves_others_intact(db_setup_and_teardown):
    alice = User(username="alice", email="alice@ex.com", is_active=True)
    bob = User(username="bob", email="bob@ex.com", is_active=True)
    await alice.save()
    await bob.save()

    await alice.delete()

    remaining = await User.objects.all()
    assert len(remaining) == 1
    assert remaining[0].username == "bob"
