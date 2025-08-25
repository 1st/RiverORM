import pytest
import pytest_asyncio

from riverorm.config import config
from riverorm.db import db
from tests.models import Product, User


@pytest_asyncio.fixture(scope="function")
async def db_setup_and_teardown():
    await db.connect(config.POSTGRES_DSN)
    await User.drop_table()
    await Product.drop_table()
    await User.create_table()
    await Product.create_table()
    yield
    await db.close()


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
async def test_all_and_select_related_stub(db_setup_and_teardown):
    await Product(name="Widget", price=10.0, description="A widget", in_stock=True).save()
    await Product(name="Gadget", price=20.0, description="A gadget", in_stock=False).save()
    all_products = await Product.all()
    assert len(all_products) == 2
    # select_related is a stub, just check it returns the class
    assert Product.select_related("orders") is Product
