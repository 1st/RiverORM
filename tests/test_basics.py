from tests.models import Order, Product, User


class TestOrderModel:
    def setup_method(self):
        self.user = User(id=1, username="john_doe", email="john_doe@work.com", is_active=True)
        self.product = Product(
            id=1,
            name="Laptop",
            price=999.99,
            description="High-performance laptop",
            in_stock=True,
        )
        self.order = Order(
            id=1,
            user=self.user,
            product=self.product,
            quantity=2,
            total_price=1999.98,
            status="pending",
        )
        self.user.orders = [self.order]
        self.product.orders = [self.order]

    def test_order_user_field(self):
        assert self.order.user.username == "john_doe"
        assert self.order.user.email == "john_doe@work.com"
        assert self.order.user.is_active is True
        assert self.order.user.id == 1

    def test_order_product_field(self):
        assert self.order.product.name == "Laptop"
        assert self.order.product.price == 999.99
        assert self.order.product.in_stock is True
        assert self.order.product.id == 1

    def test_order_fields(self):
        assert self.order.quantity == 2
        assert self.order.total_price == 1999.98
        assert self.order.status == "pending"
        assert self.order.id == 1


class TestUserModel:
    def setup_method(self):
        self.user = User(id=2, username="alice", email="alice@work.com", is_active=False)
        self.product1 = Product(
            id=2, name="Phone", price=499.99, description="Smartphone", in_stock=True
        )
        self.product2 = Product(
            id=3,
            name="Tablet",
            price=299.99,
            description="Tablet device",
            in_stock=False,
        )
        self.order1 = Order(
            id=2,
            user=self.user,
            product=self.product1,
            quantity=1,
            total_price=499.99,
            status="shipped",
        )
        self.order2 = Order(
            id=3,
            user=self.user,
            product=self.product2,
            quantity=3,
            total_price=899.97,
            status="pending",
        )
        self.user.orders = [self.order1, self.order2]
        self.product1.orders = [self.order1]
        self.product2.orders = [self.order2]

    def test_user_fields(self):
        assert self.user.username == "alice"
        assert self.user.email == "alice@work.com"
        assert self.user.is_active is False
        assert self.user.id == 2

    def test_user_orders(self):
        assert len(self.user.orders) == 2
        assert self.user.orders[0].product.name == "Phone"
        assert self.user.orders[1].product.name == "Tablet"
        assert self.user.orders[0].status == "shipped"
        assert self.user.orders[1].status == "pending"


class TestProductModel:
    def setup_method(self):
        self.user1 = User(id=3, username="bob", email="bob@work.com", is_active=True)
        self.user2 = User(id=4, username="eve", email="eve@work.com", is_active=False)
        self.product = Product(
            id=4, name="Monitor", price=199.99, description="HD Monitor", in_stock=True
        )
        self.order1 = Order(
            id=4,
            user=self.user1,
            product=self.product,
            quantity=1,
            total_price=199.99,
            status="delivered",
        )
        self.order2 = Order(
            id=5,
            user=self.user2,
            product=self.product,
            quantity=2,
            total_price=399.98,
            status="pending",
        )
        self.product.orders = [self.order1, self.order2]
        self.user1.orders = [self.order1]
        self.user2.orders = [self.order2]

    def test_product_fields(self):
        assert self.product.name == "Monitor"
        assert self.product.price == 199.99
        assert self.product.in_stock is True
        assert self.product.id == 4

    def test_product_orders(self):
        assert len(self.product.orders) == 2
        assert self.product.orders[0].user.username == "bob"
        assert self.product.orders[1].user.username == "eve"
        assert self.product.orders[0].status == "delivered"
        assert self.product.orders[1].status == "pending"


# Additional field lookup tests
def test_field_types_and_lookup():
    user = User(id=10, username="testuser", email="test@work.com", is_active=True)
    product = Product(
        id=20,
        name="Keyboard",
        price=49.99,
        description="Mechanical keyboard",
        in_stock=False,
    )
    order = Order(
        id=30,
        user=user,
        product=product,
        quantity=5,
        total_price=249.95,
        status="pending",
    )
    user.orders = [order]
    product.orders = [order]

    # Direct field lookups
    assert user.id == 10
    assert user.username == "testuser"
    assert user.is_active is True
    assert product.id == 20
    assert product.in_stock is False
    assert order.id == 30
    assert order.status == "pending"

    # Nested lookups
    assert order.user.email == "test@work.com"
    assert order.product.name == "Keyboard"
    assert user.orders[0].product.price == 49.99
    assert product.orders[0].user.username == "testuser"
