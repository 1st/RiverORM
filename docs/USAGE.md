# RiverORM Usage Guide

RiverORM is a minimalistic, async-first ORM for Python, designed for simplicity and modern development. This guide covers the basics of defining models and using RiverORM in your project.

First, ensure you have RiverORM installed. See the [Installation Guide](./INSTALL.md) for details.

## Defining Models

Models in RiverORM inherit from `Model` and use type annotations with `Field` for schema definition. Fields support Pydantic validation and metadata.

Example:

```python
from riverorm import Field, Model

class Product(Model):
    id: int = Field(pk=True)
    name: str
    price: float
    in_stock: bool = Field(True)
```

## Relationships

You can define relationships using type annotations. For example, a `User` with a list of `Order` objects:

```python
class User(Model):
    id: int
    username: str
    orders: list["Order"] = Field(default_factory=list)


class Order(Model):
    id: int
    user: User
    product: Product
```

## Creating and Using Model Instances

Model instances are created like Pydantic models:

```python
user = User(id=1, username="alice")
product = Product(id=1, name="Laptop", price=999.99)
order = Order(id=1, user=user, product=product)
```

## Async Usage

All database operations are async. Example (API subject to change):

```python
# Load a product
product = await Product.get(id=1)
# Or products with a filter
products = await Product.filter(in_stock=True)
# Update a product
product.name = "Apple Laptop"
# And save changes
await product.save()
```

## More Information

- See the [Project Overview](../README.md) for design philosophy.
- See [tests/models.py](../tests/models.py) for more model examples.

---

For advanced usage and API reference, see future documentation updates.
