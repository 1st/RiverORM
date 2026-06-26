"""Comprehensive relation-loading tests for select_related() and load_related().

Covers both backends (parametrized via conftest): forward to-one JOINs, NULL
foreign keys, multiple relations, reverse and nested batched prefetch, empty
result sets, dedupe, batched (no-N+1) query counts, composition with the rest of
the query API, and relation exclusion in serialization.
"""

from __future__ import annotations

import pytest

from tests.models import Order, Product, User


async def _make_user(username: str = "alice") -> User:
    return await User(username=username, email=f"{username}@ex.com", is_active=True).save()


async def _make_product(user_id: int | None, name: str = "Widget", price: float = 10.0) -> Product:
    return await Product(
        name=name, price=price, description=f"{name} desc", in_stock=True, user_id=user_id
    ).save()


async def _make_order(user_id: int | None, product_id: int | None, qty: int = 1) -> Order:
    return await Order(
        user_id=user_id, product_id=product_id, quantity=qty, total_price=qty * 10.0
    ).save()


# ---------------------------------------------------------------------------
# select_related — JOIN-based forward (to-one) loading
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_select_related_forward_to_one(db_setup_and_teardown):
    user = await _make_user("alice")
    product = await _make_product(user.id)

    products = await Product.select_related("user").filter(id=product.id)

    assert len(products) == 1
    assert isinstance(products[0].user, User)
    assert products[0].user.id == user.id
    assert products[0].user.username == "alice"


@pytest.mark.asyncio
async def test_select_related_multiple_relations_in_one_query(db_setup_and_teardown):
    user = await _make_user("bob")
    product = await _make_product(user.id, name="Gadget")
    order = await _make_order(user.id, product.id, qty=3)

    orders = await Order.select_related("user", "product").filter(id=order.id)

    assert len(orders) == 1
    assert orders[0].user.id == user.id
    assert orders[0].product.id == product.id
    assert orders[0].product.name == "Gadget"


@pytest.mark.asyncio
async def test_select_related_null_fk_yields_none(db_setup_and_teardown):
    # Product with no owner — LEFT JOIN must leave .user as None, not raise.
    product = await _make_product(user_id=None)

    products = await Product.select_related("user").filter(id=product.id)

    assert len(products) == 1
    assert products[0].user is None


@pytest.mark.asyncio
async def test_select_related_composes_with_filter_and_order(db_setup_and_teardown):
    user = await _make_user("carol")
    await _make_product(user.id, name="A", price=30.0)
    await _make_product(user.id, name="B", price=10.0)
    await _make_product(user.id, name="C", price=20.0)

    products = await Product.select_related("user").filter(user_id=user.id).order_by("price")

    assert [p.name for p in products] == ["B", "C", "A"]
    assert all(p.user.id == user.id for p in products)


@pytest.mark.asyncio
async def test_select_related_with_limit(db_setup_and_teardown):
    user = await _make_user("dave")
    for i in range(5):
        await _make_product(user.id, name=f"P{i}")

    products = await Product.select_related("user").order_by("id").limit(2)

    assert len(products) == 2
    assert all(isinstance(p.user, User) for p in products)


@pytest.mark.asyncio
async def test_select_related_empty_result(db_setup_and_teardown):
    products = await Product.select_related("user").filter(id=999999)
    assert products == []


@pytest.mark.asyncio
async def test_select_related_unknown_relation_raises(db_setup_and_teardown):
    with pytest.raises(ValueError):
        await Product.select_related("nonexistent").all()


# ---------------------------------------------------------------------------
# load_related — batched prefetch (forward / reverse / nested)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_related_forward_fk(db_setup_and_teardown):
    user = await _make_user("eve")
    product = await _make_product(user.id)
    order = await _make_order(user.id, product.id)

    orders = await Order.load_related("user").filter(id=order.id)

    assert orders[0].user.id == user.id


@pytest.mark.asyncio
async def test_load_related_forward_null_fk_is_none(db_setup_and_teardown):
    order = await _make_order(user_id=None, product_id=None)

    orders = await Order.load_related("user").filter(id=order.id)

    assert orders[0].user is None


@pytest.mark.asyncio
async def test_load_related_reverse_collection(db_setup_and_teardown):
    user = await _make_user("frank")
    p1 = await _make_product(user.id, name="One")
    p2 = await _make_product(user.id, name="Two")
    o1 = await _make_order(user.id, p1.id)
    o2 = await _make_order(user.id, p2.id)

    users = await User.load_related("products", "orders").filter(id=user.id)

    u = users[0]
    assert {p.id for p in u.products} == {p1.id, p2.id}
    assert {o.id for o in u.orders} == {o1.id, o2.id}


@pytest.mark.asyncio
async def test_load_related_reverse_empty_is_empty_list(db_setup_and_teardown):
    user = await _make_user("grace")  # no products, no orders

    users = await User.load_related("products", "orders").filter(id=user.id)

    assert users[0].products == []
    assert users[0].orders == []


@pytest.mark.asyncio
async def test_load_related_nested(db_setup_and_teardown):
    user = await _make_user("heidi")
    product = await _make_product(user.id)
    order = await _make_order(user.id, product.id)

    orders = await Order.load_related("product__user").filter(id=order.id)

    o = orders[0]
    assert o.product.id == product.id
    assert o.product.user.id == user.id


@pytest.mark.asyncio
async def test_load_related_forward_dedupe_shared_parent(db_setup_and_teardown):
    # Two orders share one user/product; prefetch must attach the same data to both.
    user = await _make_user("ivan")
    product = await _make_product(user.id)
    o1 = await _make_order(user.id, product.id)
    o2 = await _make_order(user.id, product.id)

    orders = await Order.load_related("user", "product").filter(user_id=user.id).order_by("id")

    assert {o.id for o in orders} == {o1.id, o2.id}
    assert all(o.user.id == user.id for o in orders)
    assert all(o.product.id == product.id for o in orders)


@pytest.mark.asyncio
async def test_load_related_empty_result(db_setup_and_teardown):
    users = await User.load_related("orders").filter(id=999999)
    assert users == []


@pytest.mark.asyncio
async def test_load_related_reverse_is_batched_no_n_plus_one(db_setup_and_teardown, monkeypatch):
    # 3 users, each with 2 orders. A correct batched prefetch issues exactly two
    # queries (one for users, one for all their orders) — never one-per-user.
    users = [await _make_user(f"user{i}") for i in range(3)]
    for u in users:
        product = await _make_product(u.id)
        await _make_order(u.id, product.id)
        await _make_order(u.id, product.id)

    db = User.db()
    original_fetch = db.fetch
    calls = 0

    async def counting_fetch(query, *args):
        nonlocal calls
        calls += 1
        return await original_fetch(query, *args)

    monkeypatch.setattr(db, "fetch", counting_fetch)

    loaded = await User.load_related("orders").filter(id__in=[u.id for u in users])

    assert len(loaded) == 3
    assert all(len(u.orders) == 2 for u in loaded)
    assert calls == 2  # 1 (users) + 1 (batched orders), independent of user count


# ---------------------------------------------------------------------------
# Serialization interaction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_to_dict_excludes_relations_by_default(db_setup_and_teardown):
    user = await _make_user("judy")
    product = await _make_product(user.id)

    loaded = (await Product.select_related("user").filter(id=product.id))[0]

    d = loaded.to_dict()
    assert "user" not in d
    assert d["user_id"] == user.id

    full = loaded.to_dict(exclude_virtual=False)
    assert full["user"]["id"] == user.id
