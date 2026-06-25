"""Tests for QuerySet.only() and QuerySet.defer() with typed FieldRef / Model.f."""

from __future__ import annotations

import pytest

from riverorm import FieldRef
from tests.models import Order, Product, User


@pytest.fixture
def db_models() -> list[type]:
    return [Order, Product, User]


# ---------------------------------------------------------------------------
# FieldRef unit tests
# ---------------------------------------------------------------------------


def test_field_ref_stores_name():
    ref = FieldRef("username")
    assert ref.name == "username"


def test_field_ref_repr():
    assert repr(FieldRef("username")) == "FieldRef('username')"


# ---------------------------------------------------------------------------
# FieldsNamespace (Model.f) unit tests
# ---------------------------------------------------------------------------


def test_model_f_returns_field_ref():
    ref = User.f.username
    assert isinstance(ref, FieldRef)
    assert ref.name == "username"


def test_model_f_unknown_field_raises():
    with pytest.raises(AttributeError, match="no real field"):
        _ = User.f.nonexistent


def test_model_f_virtual_field_raises():
    with pytest.raises(AttributeError, match="no real field"):
        _ = User.f.products


def test_model_f_dir_lists_real_fields():
    names = dir(User.f)
    assert "id" in names
    assert "username" in names
    assert "email" in names
    assert "is_active" in names
    assert "products" not in names
    assert "orders" not in names


# ---------------------------------------------------------------------------
# QuerySet.only() unit tests (no DB)
# ---------------------------------------------------------------------------


def test_only_stores_field_names():
    qs = User.objects.only(User.f.id, User.f.username)
    assert qs.only_fields == ("id", "username")
    assert qs.defer_fields == ()


def test_only_string_backward_compat():
    qs = User.objects.only("id", "username")
    assert qs.only_fields == ("id", "username")


def test_only_clears_defer():
    qs = User.objects.defer(User.f.email).only(User.f.id, User.f.username)
    assert qs.only_fields == ("id", "username")
    assert qs.defer_fields == ()


def test_only_empty_args_clears():
    qs = User.objects.only(User.f.username).only()
    assert qs.only_fields == ()


def test_only_rejects_unknown_field_ref():
    with pytest.raises(ValueError, match="Unknown fields for only"):
        User.objects.only(FieldRef("nonexistent"))


def test_only_rejects_unknown_string():
    with pytest.raises(ValueError, match="Unknown fields for only"):
        User.objects.only("nonexistent_field")


def test_only_rejects_virtual_field():
    with pytest.raises(ValueError, match="Unknown fields for only"):
        User.objects.only("products")


# ---------------------------------------------------------------------------
# QuerySet.defer() unit tests (no DB)
# ---------------------------------------------------------------------------


def test_defer_stores_field_names():
    qs = User.objects.defer(User.f.email)
    assert qs.defer_fields == ("email",)
    assert qs.only_fields == ()


def test_defer_string_backward_compat():
    qs = User.objects.defer("email")
    assert qs.defer_fields == ("email",)


def test_defer_clears_only():
    qs = User.objects.only(User.f.id, User.f.username).defer(User.f.email)
    assert qs.defer_fields == ("email",)
    assert qs.only_fields == ()


def test_defer_empty_args_clears():
    qs = User.objects.defer(User.f.email).defer()
    assert qs.defer_fields == ()


def test_defer_rejects_unknown_field_ref():
    with pytest.raises(ValueError, match="Unknown fields for defer"):
        User.objects.defer(FieldRef("nonexistent"))


def test_defer_rejects_unknown_string():
    with pytest.raises(ValueError, match="Unknown fields for defer"):
        User.objects.defer("nonexistent_field")


def test_defer_rejects_virtual_field():
    with pytest.raises(ValueError, match="Unknown fields for defer"):
        User.objects.defer("orders")


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_only_loads_named_fields(db_setup_and_teardown):
    await User(username="alice", email="alice@ex.com", is_active=True).save()

    users = await User.objects.only(User.f.id, User.f.username).all()

    assert len(users) == 1
    assert users[0].username == "alice"
    assert users[0].id is not None


@pytest.mark.asyncio
async def test_only_always_loads_primary_key(db_setup_and_teardown):
    # PK is loaded even when not named, so the instance stays identity-safe.
    await User(username="alice", email="alice@ex.com", is_active=True).save()

    users = await User.objects.only(User.f.username).all()

    assert users[0].id is not None


@pytest.mark.asyncio
async def test_defer_never_drops_primary_key(db_setup_and_teardown):
    # Deferring the PK is ignored — it is always fetched.
    await User(username="alice", email="alice@ex.com", is_active=True).save()

    users = await User.objects.defer(User.f.id, User.f.email).all()

    assert users[0].id is not None


@pytest.mark.asyncio
async def test_only_result_is_persisted(db_setup_and_teardown):
    await User(username="alice", email="alice@ex.com", is_active=True).save()

    users = await User.objects.only(User.f.id, User.f.username).all()

    assert users[0]._persisted is True


@pytest.mark.asyncio
async def test_defer_excludes_named_field(db_setup_and_teardown):
    await User(username="bob", email="bob@ex.com", is_active=True).save()

    users = await User.objects.defer(User.f.email).all()

    assert len(users) == 1
    assert users[0].username == "bob"
    assert users[0].email is None  # default applied for un-fetched optional field


@pytest.mark.asyncio
async def test_defer_result_is_persisted(db_setup_and_teardown):
    await User(username="bob", email="bob@ex.com", is_active=True).save()

    users = await User.objects.defer(User.f.email).all()

    assert users[0]._persisted is True


@pytest.mark.asyncio
async def test_only_composes_with_filter(db_setup_and_teardown):
    await User(username="alice", email="alice@ex.com", is_active=True).save()
    await User(username="bob", email="bob@ex.com", is_active=False).save()

    users = await User.objects.only(User.f.id, User.f.username).filter(is_active=True).all()

    assert len(users) == 1
    assert users[0].username == "alice"


@pytest.mark.asyncio
async def test_defer_composes_with_filter(db_setup_and_teardown):
    await User(username="alice", email="alice@ex.com", is_active=True).save()
    await User(username="bob", email="bob@ex.com", is_active=False).save()

    users = await User.objects.defer(User.f.email).filter(is_active=False).all()

    assert len(users) == 1
    assert users[0].username == "bob"


@pytest.mark.asyncio
async def test_only_composes_with_order_by(db_setup_and_teardown):
    await User(username="charlie", email="c@ex.com", is_active=True).save()
    await User(username="alice", email="a@ex.com", is_active=True).save()

    users = await User.objects.only(User.f.id, User.f.username).order_by("username").all()

    assert [u.username for u in users] == ["alice", "charlie"]


@pytest.mark.asyncio
async def test_only_first(db_setup_and_teardown):
    await User(username="carol", email="carol@ex.com", is_active=True).save()

    user = await User.objects.only(User.f.id, User.f.username).first()

    assert user is not None
    assert user.username == "carol"


@pytest.mark.asyncio
async def test_defer_multiple_fields(db_setup_and_teardown):
    await User(username="alice", email="alice@ex.com", is_active=True).save()

    users = await User.objects.defer(User.f.email, User.f.is_active).all()

    assert len(users) == 1
    assert users[0].username == "alice"
    assert users[0].id is not None


@pytest.mark.asyncio
async def test_only_via_model_classmethod(db_setup_and_teardown):
    await User(username="dave", email="dave@ex.com", is_active=True).save()

    users = await User.only(User.f.id, User.f.username).all()

    assert users[0].username == "dave"


@pytest.mark.asyncio
async def test_defer_via_model_classmethod(db_setup_and_teardown):
    await User(username="eve", email="eve@ex.com", is_active=True).save()

    users = await User.defer(User.f.email).all()

    assert users[0].username == "eve"


@pytest.mark.asyncio
async def test_only_string_compat_integration(db_setup_and_teardown):
    await User(username="alice", email="alice@ex.com", is_active=True).save()

    users = await User.objects.only("id", "username").all()

    assert users[0].username == "alice"


@pytest.mark.asyncio
async def test_defer_string_compat_integration(db_setup_and_teardown):
    await User(username="bob", email="bob@ex.com", is_active=True).save()

    users = await User.objects.defer("email").all()

    assert users[0].username == "bob"


@pytest.mark.asyncio
async def test_only_count_uses_full_query(db_setup_and_teardown):
    await User(username="alice", email="alice@ex.com", is_active=True).save()
    await User(username="bob", email="bob@ex.com", is_active=False).save()

    count = await User.objects.only(User.f.id, User.f.username).count()
    assert count == 2


@pytest.mark.asyncio
async def test_only_exists(db_setup_and_teardown):
    await User(username="alice", email="alice@ex.com", is_active=True).save()

    assert await User.objects.only(User.f.id).exists() is True


# ---------------------------------------------------------------------------
# Saving partially-loaded instances must not clobber un-fetched columns
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_partial_does_not_clobber_unfetched(db_setup_and_teardown):
    await User(username="alice", email="alice@ex.com", is_active=True).save()

    partial = await User.objects.only(User.f.username).first()
    partial.username = "alice2"
    await partial.save()

    # email / is_active were never fetched, so they must survive the save.
    full = await User.objects.get(username="alice2")
    assert full.email == "alice@ex.com"
    assert full.is_active is True


@pytest.mark.asyncio
async def test_save_update_fields_writes_only_named(db_setup_and_teardown):
    await User(username="bob", email="bob@ex.com", is_active=True).save()

    user = await User.objects.get(username="bob")
    user.username = "bob2"
    user.email = "ignored@ex.com"
    await user.save(update_fields=["username"])

    full = await User.objects.get(username="bob2")
    assert full.email == "bob@ex.com"  # email change was not written


@pytest.mark.asyncio
async def test_save_update_fields_unknown_raises(db_setup_and_teardown):
    await User(username="carol", email="carol@ex.com", is_active=True).save()

    user = await User.objects.get(username="carol")
    with pytest.raises(ValueError, match="Unknown update_fields"):
        await user.save(update_fields=["nope"])


@pytest.mark.asyncio
async def test_only_with_select_related_raises(db_setup_and_teardown):
    # Silently ignoring the column restriction would surprise callers; be explicit.
    with pytest.raises(ValueError, match="cannot be combined with select_related"):
        await Order.objects.only(Order.f.id).select_related("user").all()


@pytest.mark.asyncio
async def test_defer_with_select_related_raises(db_setup_and_teardown):
    with pytest.raises(ValueError, match="cannot be combined with select_related"):
        await Order.objects.defer(Order.f.quantity).select_related("user").all()
