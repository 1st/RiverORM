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
        # import re (already imported at top of file)

        def camel_to_snake(name):
            # If the name is all uppercase, just return lowercase
            if name.isupper():
                return name.lower()

            # Replace abbreviation runs (2+ capitals) with _abbr (unless at start)
            def abbr_repl(match):
                abbr = match.group(0)
                return "_" + abbr.lower()

            name = re.sub(r"(?<!^)([A-Z]{2,})(?![a-z])", abbr_repl, name)
            # Now convert remaining CamelCase to snake_case
            s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
            s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1)
            return s2.lower().strip("_")

        return getattr(cls.Meta, "table_name", None) or camel_to_snake(cls.__name__)
