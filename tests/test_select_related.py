import pytest

from tests.models import Product, User


@pytest.mark.asyncio
async def test_select_related_fetches_user_with_product(db_setup_and_teardown):
    user = await User(username="alice", email="alice@ex.com", is_active=True).save()
    product = await Product(
        name="Widget", price=10.0, description="A widget", in_stock=True, user_id=user.id
    ).save()

    # Fetch product with related user using select_related
    ProductWithUser = Product.select_related("user")
    products = await ProductWithUser.filter(id=product.id)
    assert len(products) == 1
    prod = products[0]
    # The related user should be fetched and attached
    assert hasattr(prod, "user")
    assert isinstance(prod.user, User)
    assert prod.user.id == user.id
    assert prod.user.username == "alice"


@pytest.mark.asyncio
async def test_select_related_multiple_products(db_setup_and_teardown):
    user = await User(username="bob", email="bob@ex.com", is_active=True).save()
    await Product(
        name="Widget", price=10.0, description="A widget", in_stock=True, user_id=user.id
    ).save()
    await Product(
        name="Gadget", price=20.0, description="A gadget", in_stock=False, user_id=user.id
    ).save()

    ProductWithUser = Product.select_related("user")
    products = await ProductWithUser.all()
    assert len(products) == 2
    for prod in products:
        assert hasattr(prod, "user")
        assert isinstance(prod.user, User)
        assert prod.user.id == user.id
