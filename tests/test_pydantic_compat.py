"""Pydantic compatibility tests for RiverORM's Model base class.

These tests verify that Model (which extends BaseModel) does not break any
expected Pydantic behaviour: instance access, validation, serialization, copy,
custom validators, inheritance, PrivateAttr, and ClassVar fields.
"""

from __future__ import annotations

from typing import ClassVar

import pytest
from pydantic import ValidationError, field_validator, model_validator
from pydantic.fields import FieldInfo

from riverorm import Field, Model


# ---------------------------------------------------------------------------
# Test models
# ---------------------------------------------------------------------------


class Simple(Model):
    id: int | None = Field(default=None)
    name: str = Field(...)
    score: float = Field(default=0.0)
    active: bool = Field(True)
    tags: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None)


class WithValidator(Model):
    id: int | None = Field(default=None)
    username: str = Field(...)
    email: str = Field(...)

    @field_validator("username")
    @classmethod
    def username_lower(cls, v: str) -> str:
        return v.lower()

    @model_validator(mode="after")
    def email_contains_at(self) -> WithValidator:
        if "@" not in self.email:
            raise ValueError("email must contain @")
        return self


class Parent(Model):
    id: int | None = Field(default=None)
    base_field: str = Field(...)


class Child(Parent):
    child_field: int = Field(default=42)


class WithClassVar(Model):
    id: int | None = Field(default=None)
    data: str = Field(...)
    CLASS_CONSTANT: ClassVar[str] = "constant"
    objects_count: ClassVar[int] = 0


# ---------------------------------------------------------------------------
# Instance attribute access
# ---------------------------------------------------------------------------


class TestInstanceAccess:
    def test_required_field_read(self):
        obj = Simple(name="test")
        assert obj.name == "test"

    def test_optional_field_defaults_to_none(self):
        obj = Simple(name="test")
        assert obj.notes is None

    def test_default_scalar(self):
        obj = Simple(name="test")
        assert obj.score == 0.0
        assert obj.active is True

    def test_default_factory(self):
        obj = Simple(name="test")
        assert obj.tags == []

    def test_provided_values(self):
        obj = Simple(name="Alice", score=9.5, active=False, tags=["a", "b"], notes="hi")
        assert obj.name == "Alice"
        assert obj.score == 9.5
        assert obj.active is False
        assert obj.tags == ["a", "b"]
        assert obj.notes == "hi"

    def test_field_mutation_updates_value(self):
        obj = Simple(name="old")
        obj.name = "new"
        assert obj.name == "new"

    def test_id_defaults_none(self):
        assert Simple(name="test").id is None

    def test_id_set_explicitly(self):
        assert Simple(id=42, name="test").id == 42

    def test_two_instances_independent(self):
        a = Simple(name="alice")
        b = Simple(name="bob")
        assert a.name == "alice"
        assert b.name == "bob"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_required_field_missing_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            Simple()  # type: ignore[call-arg]
        fields = {e["loc"][0] for e in exc_info.value.errors()}
        assert "name" in fields

    def test_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            Simple(name="x", score="not-a-float")

    def test_field_validator_runs(self):
        obj = WithValidator(username="ALICE", email="a@b.com")
        assert obj.username == "alice"

    def test_model_validator_runs(self):
        with pytest.raises(ValidationError):
            WithValidator(username="alice", email="no-at-sign")

    def test_model_validate_from_dict(self):
        obj = Simple.model_validate({"name": "from-dict", "score": 3.14})
        assert obj.name == "from-dict"
        assert obj.score == pytest.approx(3.14)

    def test_model_validate_invalid_raises(self):
        with pytest.raises(ValidationError):
            Simple.model_validate({"score": "bad"})

    def test_extra_fields_ignored(self):
        obj = Simple.model_validate({"name": "x", "unknown_key": 99})
        assert obj.name == "x"


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_model_dump_returns_dict(self):
        d = Simple(name="dump-test", score=1.0).model_dump()
        assert isinstance(d, dict)
        assert d["name"] == "dump-test"
        assert d["score"] == 1.0

    def test_model_dump_includes_all_fields(self):
        d = Simple(name="x").model_dump()
        assert set(d.keys()) >= {"id", "name", "score", "active", "tags", "notes"}

    def test_model_dump_json_roundtrip(self):
        obj = Simple(name="json", score=2.5, tags=["x"])
        parsed = Simple.model_validate_json(obj.model_dump_json())
        assert parsed.name == "json"
        assert parsed.score == pytest.approx(2.5)
        assert parsed.tags == ["x"]

    def test_model_dump_exclude_none(self):
        d = Simple(name="x").model_dump(exclude_none=True)
        assert "notes" not in d
        assert "name" in d

    def test_to_dict_helper(self):
        assert Simple(name="x").to_dict()["name"] == "x"

    def test_to_json_helper(self):
        assert "x" in Simple(name="x").to_json()


# ---------------------------------------------------------------------------
# model_construct (bypasses validation)
# ---------------------------------------------------------------------------


class TestModelConstruct:
    def test_construct_with_fields(self):
        obj = Simple.model_construct(name="constructed", score=7.0)
        assert obj.name == "constructed"
        assert obj.score == 7.0

    def test_construct_allows_partial(self):
        obj = Simple.model_construct(score=5.0)
        assert obj.score == 5.0

    def test_construct_skips_validators(self):
        obj = WithValidator.model_construct(username="UPPER", email="no-at")
        assert obj.username == "UPPER"

    def test_construct_persisted_false(self):
        assert Simple.model_construct(name="x")._persisted is False


# ---------------------------------------------------------------------------
# model_copy
# ---------------------------------------------------------------------------


class TestModelCopy:
    def test_copy_is_new_instance(self):
        obj = Simple(name="original")
        assert obj.model_copy() is not obj

    def test_copy_preserves_values(self):
        copy = Simple(name="orig", score=3.0).model_copy()
        assert copy.name == "orig"
        assert copy.score == 3.0

    def test_copy_with_update(self):
        obj = Simple(name="orig", score=1.0)
        copy = obj.model_copy(update={"score": 99.0})
        assert copy.score == 99.0
        assert obj.score == 1.0

    def test_deep_copy(self):
        obj = Simple(name="x", tags=["a"])
        obj.model_copy(deep=True).tags.append("b")
        assert obj.tags == ["a"]


# ---------------------------------------------------------------------------
# model_fields introspection
# ---------------------------------------------------------------------------


class TestModelFieldsIntrospection:
    def test_model_fields_is_dict(self):
        assert isinstance(Simple.model_fields, dict)

    def test_model_fields_contains_expected_keys(self):
        assert {"id", "name", "score"} <= set(Simple.model_fields)

    def test_model_fields_values_are_field_info(self):
        for name, field in Simple.model_fields.items():
            assert isinstance(field, FieldInfo), f"{name} should be FieldInfo"

    def test_model_real_fields(self):
        assert "name" in Simple.model_real_fields()

    def test_classvar_not_in_model_fields(self):
        assert "CLASS_CONSTANT" not in WithClassVar.model_fields
        assert "objects_count" not in WithClassVar.model_fields

    def test_classvar_accessible_on_class(self):
        assert WithClassVar.CLASS_CONSTANT == "constant"
        assert WithClassVar.objects_count == 0


# ---------------------------------------------------------------------------
# Inheritance
# ---------------------------------------------------------------------------


class TestInheritance:
    def test_child_inherits_parent_fields(self):
        obj = Child(base_field="hello")
        assert obj.base_field == "hello"
        assert obj.child_field == 42

    def test_child_model_fields_includes_inherited(self):
        assert "base_field" in Child.model_fields
        assert "child_field" in Child.model_fields

    def test_parent_model_fields_unchanged(self):
        assert "child_field" not in Parent.model_fields

    def test_isinstance_chain(self):
        obj = Child(base_field="x")
        assert isinstance(obj, Child)
        assert isinstance(obj, Parent)
        assert isinstance(obj, Model)

    def test_child_default_not_corrupted(self):
        # Regression: metaclass-based FieldRef previously corrupted inherited
        # field defaults in subclasses (e.g. Child.id.default became FieldRef).
        assert Child.model_fields["id"].default is None
        assert Child(base_field="x").id is None


# ---------------------------------------------------------------------------
# PrivateAttr
# ---------------------------------------------------------------------------


class TestPrivateAttr:
    def test_persisted_defaults_false(self):
        assert Simple(name="x")._persisted is False

    def test_persisted_can_be_set(self):
        obj = Simple(name="x")
        obj._persisted = True
        assert obj._persisted is True

    def test_persisted_not_in_model_dump(self):
        obj = Simple(name="x")
        obj._persisted = True
        assert "_persisted" not in obj.model_dump()

    def test_persisted_not_in_model_fields(self):
        assert "_persisted" not in Simple.model_fields
