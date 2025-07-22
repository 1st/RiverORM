import re

from pydantic import BaseModel, Field


class Model(BaseModel):
    """
    Base model class for River ORM.

    This class can be extended to create specific models.
    """

    id: int = Field(..., description="Unique identifier for the model instance")

    class Meta:
        table_name: str
        primary_key: str = "id"

    class Config:
        from_attributes = True
        validate_by_name = True
        use_enum_values = True
        arbitrary_types_allowed = True

    @classmethod
    def table_name(cls):
        def camel_to_snake(name):
            name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
            name = re.sub("([a-z])([A-Z0-9])", r"\1_\2", name)
            return name.lower()

        return getattr(cls.Meta, "table_name", None) or camel_to_snake(cls.__name__)
