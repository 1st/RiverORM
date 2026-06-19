from riverorm import Field, Model


class User(Model):
    """
    User model representing a user in the system.
    """

    id: int | None = Field(default=None, description="User ID")
    username: str = Field(description="Username of the user")
    email: str | None = Field(default=None, description="Email address of the user")
    is_active: bool = Field(True, description="Is the user active?")
    # Reverse relations (populated by load_related), never stored as columns.
    products: list["Product"] = Field(default_factory=list, description="Products owned by user")
    orders: list["Order"] = Field(default_factory=list, description="Orders placed by the user")


class Product(Model):
    """
    Product model representing a product in the system.
    """

    id: int | None = Field(default=None, description="Product ID")
    name: str = Field(description="Name of the product")
    price: float = Field(description="Price of the product")
    description: str = Field(description="Description of the product")
    in_stock: bool = Field(True, description="Is the product in stock?")
    user_id: int | None = Field(default=None, description="Owner user id of the product")
    # Forward and reverse relations (populated by select_related / load_related).
    user: "User | None" = Field(default=None, description="Owner of the product")
    orders: list["Order"] = Field(default_factory=list, description="Orders for this product")


class Order(Model):
    """
    Order model representing an order in the system.
    """

    id: int | None = Field(default=None, description="Order ID")
    quantity: int = Field(description="Quantity of the product ordered")
    total_price: float = Field(description="Total price of the order")
    status: str = Field("pending", description="Order status")
    user_id: int | None = Field(default=None, description="User who placed the order")
    product_id: int | None = Field(default=None, description="Product ordered")
    # Forward relations (populated by select_related / load_related).
    user: "User | None" = Field(default=None, description="User who placed the order")
    product: "Product | None" = Field(default=None, description="Product ordered")
