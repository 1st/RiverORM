from riverorm import Field, Model


class User(Model):
    """
    User model representing a user in the system.
    """

    id: int | None = Field(default=None, description="User ID")
    username: str = Field(..., description="Username of the user")
    email: str | None = Field(..., description="Email address of the user")
    is_active: bool = Field(True, description="Is the user active?")
    orders: list["Order"] = Field(default_factory=list, description="Orders placed by the user")


class Product(Model):
    """
    Product model representing a product in the system.
    """

    id: int | None = Field(..., description="Product ID")
    name: str = Field(..., description="Name of the product")
    price: float = Field(..., description="Price of the product")
    description: str = Field(..., description="Description of the product")
    in_stock: bool = Field(True, description="Is the product in stock?")
    orders: list["Order"] = Field(default_factory=list, description="Orders for this product")


class Order(Model):
    """
    Order model representing an order in the system.
    """

    id: int | None = Field(..., description="Order ID")
    user: User = Field(..., description="User who placed the order")
    product: Product = Field(..., description="Product ordered")
    quantity: int = Field(..., description="Quantity of the product ordered")
    total_price: float = Field(..., description="Total price of the order")
    status: str = Field("pending", description="Order status")
