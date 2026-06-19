import pytest
from pydantic import ValidationError

from riverorm import Field, Model, PrimaryKeyError


class Sku(Model):
    """Model whose primary key is a non-``id`` string column."""

    sku: str = Field(primary_key=True, description="Stock keeping unit")
    name: str = Field(description="Product name")
    price: float = Field(default=0.0, description="Price")


class IntPkThing(Model):
    """Model with the default auto-increment integer ``id`` primary key."""

    id: int | None = Field(default=None)
    label: str = Field()


class Bounded(Model):
    code: str = Field(max_length=5)


@pytest.fixture
def db_models() -> list[type[Model]]:
    """Override conftest's ``db_models`` so the shared setup/teardown fixture
    creates and drops this module's tables on both backends."""
    return [Sku, IntPkThing]


def test_primary_key_resolution():
    assert Sku.primary_key() == "sku"
    assert IntPkThing.primary_key() == "id"


def test_field_meta_roundtrip():
    meta = Sku._field_meta("sku")
    assert meta.primary_key is True
    assert IntPkThing._field_meta("id").primary_key is False


def test_pk_kwarg_deprecated():
    with pytest.warns(DeprecationWarning):

        class Legacy(Model):
            code: str = Field(pk=True)

    assert Legacy.primary_key() == "code"


def test_max_length_validation():
    Bounded(code="abcde")  # exactly max_length is fine
    with pytest.raises(ValidationError):
        Bounded(code="toolong")


def test_existing_field_calls_still_work():
    # Field(default=None), Field(default_factory=list), positional default.
    class M(Model):
        a: str | None = Field(default=None)
        b: list[int] = Field(default_factory=list)
        c: bool = Field(True, description="flag")

    m = M()
    assert m.a is None
    assert m.b == []
    assert m.c is True


def test_pk_mutation_protected_in_memory():
    thing = IntPkThing(id=5, label="x")
    # Mark as persisted to simulate a stored row.
    thing._persisted = True
    with pytest.raises(PrimaryKeyError):
        thing.id = 6
    # Same value is allowed.
    thing.id = 5


def test_pk_none_to_value_allowed():
    thing = IntPkThing(label="x")
    assert thing.id is None
    thing.id = 42  # None -> value transition allowed
    assert thing.id == 42


@pytest.mark.asyncio
async def test_string_pk_roundtrip(db_setup_and_teardown):
    obj = Sku(sku="ABC-123", name="Widget", price=9.99)
    await obj.save()
    fetched = await Sku.get(sku="ABC-123")
    assert fetched is not None
    assert fetched.sku == "ABC-123"
    assert fetched.name == "Widget"
    assert fetched.price == pytest.approx(9.99, rel=1e-3)

    # Update path: change a non-PK field and re-save.
    fetched.name = "Gadget"
    await fetched.save()
    again = await Sku.get(sku="ABC-123")
    assert again is not None
    assert again.name == "Gadget"


@pytest.mark.asyncio
async def test_string_pk_mutation_raises_after_fetch(db_setup_and_teardown):
    obj = Sku(sku="X1", name="N", price=1.0)
    await obj.save()
    fetched = await Sku.get(sku="X1")
    assert fetched is not None
    with pytest.raises(PrimaryKeyError):
        fetched.sku = "X2"


@pytest.mark.asyncio
async def test_int_pk_roundtrip(db_setup_and_teardown):
    obj = IntPkThing(label="hello")
    await obj.save()
    assert obj.id is not None
    fetched = await IntPkThing.get(id=obj.id)
    assert fetched is not None
    assert fetched.label == "hello"
