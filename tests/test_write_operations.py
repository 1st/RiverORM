"""Tests for write-side QuerySet operations: create, update, delete, get_or_create."""

import pytest

from tests.models import User


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_inserts_and_returns_instance(db_setup_and_teardown):
    user = await User.objects.create(username="alice", email="alice@ex.com", is_active=True)
    assert user.id is not None
    assert user.username == "alice"
    assert user._persisted is True


@pytest.mark.asyncio
async def test_model_create_classmethod(db_setup_and_teardown):
    # Model.create() is the classmethod shorthand
    user = await User.create(username="bob", email="bob@ex.com", is_active=False)
    assert user.id is not None
    fetched = await User.objects.get(username="bob")
    assert fetched.id == user.id
    assert fetched.is_active is False


@pytest.mark.asyncio
async def test_create_chained_with_save_equivalent(db_setup_and_teardown):
    # create() is exactly equivalent to Model().save()
    by_save = User(username="carol", email="carol@ex.com", is_active=True)
    await by_save.save()
    await User.objects.create(username="dave", email="dave@ex.com", is_active=True)

    users = await User.objects.order_by("id").all()
    assert [u.username for u in users] == ["carol", "dave"]
    assert users[0]._persisted is True
    assert users[1]._persisted is True


# ---------------------------------------------------------------------------
# QuerySet.update()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_all_matching_rows(db_setup_and_teardown):
    await User.objects.create(username="alice", is_active=True)
    await User.objects.create(username="bob", is_active=True)
    await User.objects.create(username="carol", is_active=False)

    count = await User.objects.filter(is_active=True).update(is_active=False)
    assert count == 2

    still_active = await User.objects.filter(is_active=True).count()
    assert still_active == 0
    total = await User.objects.count()
    assert total == 3


@pytest.mark.asyncio
async def test_update_multiple_fields(db_setup_and_teardown):
    user = await User.objects.create(username="alice", email="old@ex.com", is_active=True)

    await User.objects.filter(id=user.id).update(username="alice2", email="new@ex.com")

    updated = await User.objects.get(id=user.id)
    assert updated.username == "alice2"
    assert updated.email == "new@ex.com"


@pytest.mark.asyncio
async def test_update_returns_zero_when_no_match(db_setup_and_teardown):
    count = await User.objects.filter(username="ghost").update(is_active=False)
    assert count == 0


@pytest.mark.asyncio
async def test_manager_update_updates_all_rows(db_setup_and_teardown):
    await User.objects.create(username="alice", is_active=True)
    await User.objects.create(username="bob", is_active=True)

    count = await User.objects.update(is_active=False)
    assert count == 2
    assert await User.objects.filter(is_active=True).count() == 0


# ---------------------------------------------------------------------------
# QuerySet.delete()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_matching_rows(db_setup_and_teardown):
    await User.objects.create(username="alice", is_active=True)
    await User.objects.create(username="bob", is_active=False)
    await User.objects.create(username="carol", is_active=False)

    count = await User.objects.filter(is_active=False).delete()
    assert count == 2

    remaining = await User.objects.all()
    assert len(remaining) == 1
    assert remaining[0].username == "alice"


@pytest.mark.asyncio
async def test_delete_returns_zero_when_no_match(db_setup_and_teardown):
    count = await User.objects.filter(username="ghost").delete()
    assert count == 0


@pytest.mark.asyncio
async def test_manager_delete_removes_all_rows(db_setup_and_teardown):
    await User.objects.create(username="alice", is_active=True)
    await User.objects.create(username="bob", is_active=True)

    count = await User.objects.delete()
    assert count == 2
    assert await User.objects.count() == 0


# ---------------------------------------------------------------------------
# get_or_create()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_or_create_creates_when_missing(db_setup_and_teardown):
    user, created = await User.objects.get_or_create(
        username="alice",
        defaults={"email": "alice@ex.com", "is_active": True},
    )
    assert created is True
    assert user.id is not None
    assert user.username == "alice"
    assert user.email == "alice@ex.com"


@pytest.mark.asyncio
async def test_get_or_create_returns_existing_without_update(db_setup_and_teardown):
    original = await User.objects.create(
        username="alice", email="alice@ex.com", is_active=True
    )

    user, created = await User.objects.get_or_create(
        username="alice",
        defaults={"email": "different@ex.com"},  # should be ignored
    )
    assert created is False
    assert user.id == original.id
    assert user.email == "alice@ex.com"  # original value preserved


@pytest.mark.asyncio
async def test_get_or_create_no_defaults(db_setup_and_teardown):
    user, created = await User.objects.get_or_create(username="alice", is_active=True)
    assert created is True

    same, created2 = await User.objects.get_or_create(username="alice", is_active=True)
    assert created2 is False
    assert same.id == user.id
