from __future__ import annotations

import pytest

from tests.models import Order, Product, User


@pytest.mark.asyncio
async def test_load_related_fk_and_reverse(db_setup_and_teardown):
    # Create user, products, and orders
    user = await User(username="alice", email="alice@ex.com", is_active=True).save()
    prod1 = await Product(
        name="Widget", price=10.0, description="A widget", in_stock=True, user_id=user.id
    ).save()
    prod2 = await Product(
        name="Gadget", price=20.0, description="A gadget", in_stock=False, user_id=user.id
    ).save()
    order1 = await Order(user_id=user.id, product_id=prod1.id, quantity=2, total_price=20.0).save()
    order2 = await Order(user_id=user.id, product_id=prod2.id, quantity=1, total_price=20.0).save()

    # Load user with related products (FK) and orders (reverse FK)
    UserWithRelated = User.load_related("products", "orders")
    users = await UserWithRelated.filter(id=user.id)
    assert len(users) == 1
    u = users[0]
    # Should have .products and .orders attributes
    assert hasattr(u, "products")
    assert hasattr(u, "orders")
    # .products is a list of Product
    assert isinstance(u.products, list)
    assert all(isinstance(p, Product) for p in u.products)
    # .orders is a list of Order
    assert isinstance(u.orders, list)
    assert all(isinstance(o, Order) for o in u.orders)
    # Check correct objects are loaded
    assert {p.id for p in u.products} == {prod1.id, prod2.id}
    assert {o.id for o in u.orders} == {order1.id, order2.id}


@pytest.mark.asyncio
async def test_load_related_nested(db_setup_and_teardown):
    # Create user, product, order
    user = await User(username="bob", email="bob@ex.com", is_active=True).save()
    prod = await Product(
        name="Thing", price=5.0, description="A thing", in_stock=True, user_id=user.id
    ).save()
    order = await Order(user_id=user.id, product_id=prod.id, quantity=3, total_price=15.0).save()

    # Load order with user and product, and product's user
    OrderWithRelated = Order.load_related("user", "product", "product__user")
    orders = await OrderWithRelated.filter(id=order.id)
    assert len(orders) == 1
    o = orders[0]
    assert hasattr(o, "user")
    assert hasattr(o, "product")
    assert hasattr(o.product, "user")
    assert o.user.id == user.id
    assert o.product.id == prod.id
    assert o.product.user.id == user.id
