from pydantic import BaseModel, Field


class Model(BaseModel):
    """
    Base model class for River ORM.

    This class can be extended to create specific models.
    """

    id: int = Field(..., description="Unique identifier for the model instance")

    class Config:
        from_attributes = True
        validate_by_name = True
        use_enum_values = True
        arbitrary_types_allowed = True
