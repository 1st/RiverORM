import pytest

from riverorm.queryset import Manager, QuerySet
from tests.models import Order, Product, User


# -- pure / immutability (no DB) --------------------------------------------


def test_objects_returns_manager_bound_to_model():
    assert isinstance(User.objects, Manager)
    assert User.objects.model is User
    assert Product.objects.model is Product


def test_manager_returns_fresh_queryset_each_call():
    qs1 = User.objects.filter(id=1)
    qs2 = User.objects.filter(id=2)
    assert qs1 is not qs2
    assert qs1.where != qs2.where


def test_filter_is_immutable():
    base = User.objects.filter(is_active=True)
    derived = base.filter(id__gt=5)
    # original is untouched
    assert len(base.where) == 1
    assert len(derived.where) == 2
    assert base is not derived


def test_order_limit_offset_are_immutable():
    base = User.objects.filter(is_active=True)
    derived = base.order_by("-id").limit(10).offset(5)
    assert base.order == ()
    assert base.limit_value is None
    assert base.offset_value is None
    assert derived.order[0].descending is True
    assert derived.order[0].column.name == "id"
    assert derived.limit_value == 10
    assert derived.offset_value == 5


def test_order_by_parses_direction():
    qs = User.objects.order_by("name", "-id")
    assert [(o.column.name, o.descending) for o in qs.order] == [
        ("name", False),
        ("id", True),
    ]


# -- DB-backed --------------------------------------------------------------


async def _seed_users():
    await User(username="alice", email="a@ex.com", is_active=True).save()
    await User(username="bob", email="b@ex.com", is_active=False).save()
    await User(username="carol", email="c@ex.com", is_active=True).save()


@pytest.mark.asyncio
async def test_await_executes_query(db_setup_and_teardown):
    await _seed_users()
    qs = User.objects.filter(is_active=True)
    users = await qs
    assert isinstance(users, list)
    assert {u.username for u in users} == {"alice", "carol"}


@pytest.mark.asyncio
async def test_all_terminal(db_setup_and_teardown):
    await _seed_users()
    users = await User.objects.all()
    assert len(users) == 3


@pytest.mark.asyncio
async def test_order_by_limit_offset(db_setup_and_teardown):
    await _seed_users()
    users = await User.objects.order_by("-id").limit(2)
    assert [u.username for u in users] == ["carol", "bob"]

    users = await User.objects.order_by("id").limit(1).offset(1)
    assert [u.username for u in users] == ["bob"]


@pytest.mark.asyncio
async def test_async_iteration(db_setup_and_teardown):
    await _seed_users()
    names = [u.username async for u in User.objects.order_by("id")]
    assert names == ["alice", "bob", "carol"]


@pytest.mark.asyncio
async def test_exclude(db_setup_and_teardown):
    await _seed_users()
    users = await User.objects.exclude(username="bob")
    assert {u.username for u in users} == {"alice", "carol"}


@pytest.mark.asyncio
async def test_get_returns_single(db_setup_and_teardown):
    await _seed_users()
    user = await User.objects.get(username="bob")
    assert user.username == "bob"
    assert user.is_active is False


@pytest.mark.asyncio
async def test_get_raises_does_not_exist(db_setup_and_teardown):
    await _seed_users()
    with pytest.raises(User.DoesNotExist):
        await User.objects.get(username="nobody")


@pytest.mark.asyncio
async def test_get_raises_multiple(db_setup_and_teardown):
    await _seed_users()
    with pytest.raises(User.MultipleObjectsReturned):
        await User.objects.get(is_active=True)


@pytest.mark.asyncio
async def test_first(db_setup_and_teardown):
    await _seed_users()
    user = await User.objects.order_by("id").first()
    assert user is not None
    assert user.username == "alice"

    none = await User.objects.filter(username="ghost").first()
    assert none is None


@pytest.mark.asyncio
async def test_count(db_setup_and_teardown):
    await _seed_users()
    assert await User.objects.count() == 3
    assert await User.objects.filter(is_active=True).count() == 2


@pytest.mark.asyncio
async def test_exists(db_setup_and_teardown):
    await _seed_users()
    assert await User.objects.filter(is_active=True).exists() is True
    assert await User.objects.filter(username="ghost").exists() is False


@pytest.mark.asyncio
async def test_select_related_composes_with_filter(db_setup_and_teardown):
    user = await User(username="alice", email="a@ex.com", is_active=True).save()
    p1 = await Product(
        name="Widget", price=10.0, description="w", in_stock=True, user_id=user.id
    ).save()
    await Product(name="Gadget", price=20.0, description="g", in_stock=True, user_id=user.id).save()

    products = await Product.objects.select_related("user").filter(id=p1.id)
    assert len(products) == 1
    assert isinstance(products[0].user, User)
    assert products[0].user.username == "alice"

    # composes with ordering and limit
    products = await Product.objects.select_related("user").order_by("-id").limit(1)
    assert len(products) == 1
    assert isinstance(products[0].user, User)
    assert products[0].name == "Gadget"


@pytest.mark.asyncio
async def test_load_related_composes_with_ordering(db_setup_and_teardown):
    user = await User(username="alice", email="a@ex.com", is_active=True).save()
    prod = await Product(
        name="Widget", price=10.0, description="w", in_stock=True, user_id=user.id
    ).save()
    await Order(user_id=user.id, product_id=prod.id, quantity=2, total_price=20.0).save()
    await Order(user_id=user.id, product_id=prod.id, quantity=1, total_price=10.0).save()

    users = await User.objects.load_related("orders", "products").order_by("id").limit(5)
    assert len(users) == 1
    u = users[0]
    assert {p.id for p in u.products} == {prod.id}
    assert len(u.orders) == 2


def test_queryset_is_generic_alias():
    # smoke check that the type parameterizes cleanly
    qs: QuerySet[User] = User.objects.filter(id=1)
    assert qs.model is User
