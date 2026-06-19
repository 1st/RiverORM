import pytest

from tests.models import Product, User


@pytest.mark.asyncio
async def test_filter_comparison_operators(db_setup_and_teardown):
    await User(username="alice", email="alice@ex.com", is_active=True).save()
    await User(username="bob", email="bob@ex.com", is_active=False).save()
    await User(username="carol", email="carol@ex.com", is_active=True).save()

    users = await User.filter(id__gt=0)
    assert len(users) == 3

    users = await User.filter(id__lt=1000)
    assert len(users) == 3

    users = await User.filter(id__gt=1, id__lt=3)
    assert len(users) == 1
    assert users[0].username == "bob"

    users = await User.filter(username__ne="bob")
    assert len(users) == 2
    assert all(u.username != "bob" for u in users)

    users = await User.filter(username__in=["alice", "carol"])
    assert len(users) == 2
    assert {u.username for u in users} == {"alice", "carol"}

    users = await User.filter(is_active=True)
    assert len(users) == 2
    assert all(u.is_active for u in users)


@pytest.mark.asyncio
async def test_fetch_all_returns_all_objects(db_setup_and_teardown):
    await User(username="eve", email="eve@ex.com", is_active=True).save()
    await User(username="frank", email="frank@ex.com", is_active=False).save()
    await Product(name="Thing", price=5.0, description="A thing", in_stock=True, user_id=1).save()

    users = await User.all()
    products = await Product.all()

    assert len(users) == 2
    assert {u.username for u in users} == {"eve", "frank"}
    assert len(products) == 1
    assert products[0].name == "Thing"
