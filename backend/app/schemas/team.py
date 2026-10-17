from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.schemas.common import Email, Name

Role = Literal["lead", "developer", "qa"]

MAX_SKILLS = 30
MAX_SKILL_LENGTH = 50


def normalise_skills(skills: list[str]) -> list[str]:
    """Trim each skill, drop empty ones and case-insensitive duplicates (first spelling wins)."""
    result: list[str] = []
    seen: set[str] = set()
    for skill in skills:
        skill = " ".join(skill.split())
        if not skill or skill.lower() in seen:
            continue
        if len(skill) > MAX_SKILL_LENGTH:
            raise ValueError(f"Each skill must be at most {MAX_SKILL_LENGTH} characters")
        seen.add(skill.lower())
        result.append(skill)
    if len(result) > MAX_SKILLS:
        raise ValueError(f"At most {MAX_SKILLS} skills")
    return result


Skills = Annotated[list[str], AfterValidator(normalise_skills)]


class TeamMemberCreate(BaseModel):
    name: Name
    email: Email
    skills: Skills = Field(default_factory=list)
    role: Role = "developer"


class TeamMemberUpdate(BaseModel):
    """Only the fields that are sent are changed."""

    name: Name | None = None
    email: Email | None = None
    skills: Skills | None = None
    role: Role | None = None


class TeamMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    email: str
    skills: list[str]
    role: Role
    created_at: datetime
