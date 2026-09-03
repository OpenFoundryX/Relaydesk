from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Every request and response schema inherits this.

    Python stays snake_case; the wire format is camelCase, matching the
    console's TypeScript types field for field.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )
