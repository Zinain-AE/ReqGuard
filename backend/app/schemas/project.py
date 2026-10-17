from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ProjectName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
LongText = Annotated[str, Field(max_length=20_000)]


class ProjectCreate(BaseModel):
    name: ProjectName
    description: LongText = ""
    scope_text: LongText = ""


class ProjectUpdate(BaseModel):
    """Only the fields that are sent are changed."""

    name: ProjectName | None = None
    description: LongText | None = None
    scope_text: LongText | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    scope_text: str
    owner_id: int
    created_at: datetime
    updated_at: datetime
