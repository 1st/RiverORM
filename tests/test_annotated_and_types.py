"""Tests for Annotated field syntax (issue #30), DDL nullability (issue #28),
and the to_dict / to_json serialization helpers (issue #28)."""

import json
from typing import Annotated

import pytest

from riverorm import Field, Model
from riverorm.utils import is_nullable, unwrap_type


# ---------------------------------------------------------------------------
# Inline models using Annotated syntax — defined here, not in tests/models.py,
# so they don't interfere with the shared fixture setup.
# ---------------------------------------------------------------------------


class AnnotatedUser(Model):
    class Meta:
        table_name = "annotated_users"

    id: int | None = Field(default=None)
    # Annotated-style field declarations:
    username: Annotated[str, Field(max_length=50, unique=True)]
    email: Annotated[str | None, Field(default=None)]
    is_active: Annotated[bool, Field(True)]


class AnnotatedProduct(Model):
    class Meta:
        table_name = "annotated_products"

    id: int | None = Field(default=None)
    name: Annotated[str, Field(max_length=200)]
    price: Annotated[float, Field()]
    owner_id: Annotated[int | None, Field(default=None)]


# ---------------------------------------------------------------------------
# Unit tests — no DB required
# ---------------------------------------------------------------------------


class TestAnnotatedFieldMeta:
    """FieldMeta is preserved when using Annotated[T, Field(...)] syntax."""

    def test_max_length_is_readable(self):
        from riverorm.fields import field_meta

        field = AnnotatedUser.model_fields["username"]
        meta = field_meta(field)
        assert meta.max_length == 50

    def test_unique_is_readable(self):
        from riverorm.fields import field_meta

        field = AnnotatedUser.model_fields["username"]
        meta = field_meta(field)
        assert meta.unique is True

    def test_annotation_is_unwrapped_to_base_type(self):
        # Pydantic stores the base type in .annotation, not Annotated[T, ...]
        assert AnnotatedUser.model_fields["username"].annotation is str

    def test_optional_annotation_preserved(self):
        field = AnnotatedUser.model_fields["email"]
        ann = field.annotation
        # str | None
        assert is_nullable(ann)
        assert unwrap_type(ann) is str

    def test_non_nullable_field(self):
        field = AnnotatedUser.model_fields["username"]
        assert not is_nullable(field.annotation)

    def test_virtual_fields_not_present(self):
        # AnnotatedUser has no virtual (relation) fields
        assert AnnotatedUser.model_virtual_fields() == {}

    def test_real_fields_include_all_scalar_fields(self):
        real = AnnotatedUser.model_real_fields()
        assert set(real) == {"id", "username", "email", "is_active"}


# ---------------------------------------------------------------------------
# is_nullable / unwrap_type unit tests
# ---------------------------------------------------------------------------


class TestIsNullable:
    def test_plain_type_not_nullable(self):
        assert not is_nullable(int)
        assert not is_nullable(str)
        assert not is_nullable(bool)
        assert not is_nullable(float)

    def test_pep604_union_nullable(self):
        ann = int | None
        assert is_nullable(ann)

    def test_pep604_union_not_nullable(self):
        ann = int | str
        assert not is_nullable(ann)

    def test_none_type_itself(self):
        assert is_nullable(type(None))

    def test_typing_optional(self):
        from typing import Optional

        assert is_nullable(Optional[str])

    def test_typing_union_with_none(self):
        from typing import Union

        assert is_nullable(Union[str, None])

    def test_typing_union_without_none(self):
        from typing import Union

        assert not is_nullable(Union[str, int])


class TestUnwrapType:
    def test_unwraps_pep604_optional(self):
        assert unwrap_type(int | None) is int

    def test_unwraps_typing_optional(self):
        from typing import Optional

        assert unwrap_type(Optional[str]) is str

    def test_plain_type_unchanged(self):
        assert unwrap_type(str) is str

    def test_multi_union_returns_first_non_none(self):
        from typing import Union

        result = unwrap_type(Union[str, int, None])
        assert result is str


# ---------------------------------------------------------------------------
# Integration tests (require DB via db_setup_and_teardown fixture)
# ---------------------------------------------------------------------------


@pytest.fixture
def db_models():
    return [AnnotatedProduct, AnnotatedUser]


@pytest.mark.asyncio
async def test_annotated_model_create_and_fetch(db_setup_and_teardown):
    user = AnnotatedUser(username="alice", email="alice@ex.com", is_active=True)
    await user.save()

    assert user.id is not None
    assert user._persisted is True

    fetched = await AnnotatedUser.objects.get(username="alice")
    assert fetched.email == "alice@ex.com"
    assert fetched.is_active is True


@pytest.mark.asyncio
async def test_annotated_field_max_length_validated(db_setup_and_teardown):
    """Pydantic enforces max_length from Annotated[str, Field(max_length=50)]."""
    with pytest.raises(Exception):
        AnnotatedUser(username="a" * 51, is_active=True)


@pytest.mark.asyncio
async def test_nullable_column_accepts_none(db_setup_and_teardown):
    user = AnnotatedUser(username="bob", email=None, is_active=False)
    await user.save()
    fetched = await AnnotatedUser.objects.get(id=user.id)
    assert fetched.email is None


@pytest.mark.asyncio
async def test_annotated_filter_and_order(db_setup_and_teardown):
    await AnnotatedUser(username="alice", is_active=True).save()
    await AnnotatedUser(username="bob", is_active=False).save()

    active = await AnnotatedUser.objects.filter(is_active=True).all()
    assert len(active) == 1
    assert active[0].username == "alice"

    ordered = await AnnotatedUser.objects.order_by("username").all()
    assert [u.username for u in ordered] == ["alice", "bob"]


# ---------------------------------------------------------------------------
# to_dict / to_json
# ---------------------------------------------------------------------------


class TestToDictToJson:
    def test_to_dict_includes_scalar_fields(self):
        user = AnnotatedUser(id=1, username="alice", email="a@b.com", is_active=True)
        d = user.to_dict()
        assert d == {"id": 1, "username": "alice", "email": "a@b.com", "is_active": True}

    def test_to_dict_exclude_none(self):
        user = AnnotatedUser(id=None, username="alice", email=None, is_active=True)
        d = user.to_dict(exclude_none=True)
        assert "id" not in d
        assert "email" not in d
        assert d["username"] == "alice"

    def test_to_json_is_valid_json(self):
        user = AnnotatedUser(id=1, username="alice", email=None, is_active=True)
        raw = user.to_json()
        parsed = json.loads(raw)
        assert parsed["username"] == "alice"
        assert parsed["email"] is None

    def test_to_json_exclude_none(self):
        user = AnnotatedUser(id=None, username="alice", email=None, is_active=True)
        parsed = json.loads(user.to_json(exclude_none=True))
        assert "email" not in parsed
        assert "id" not in parsed


@pytest.mark.asyncio
async def test_to_dict_after_save(db_setup_and_teardown):
    user = AnnotatedUser(username="carol", email="carol@ex.com", is_active=True)
    await user.save()
    d = user.to_dict()
    assert d["id"] is not None
    assert d["username"] == "carol"
    # Virtual fields must be absent
    assert "products" not in d
    assert "orders" not in d
