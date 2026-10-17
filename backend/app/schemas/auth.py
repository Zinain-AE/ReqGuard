from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Email, Name


class RegisterIn(BaseModel):
    name: Name
    email: Email
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    created_at: datetime
