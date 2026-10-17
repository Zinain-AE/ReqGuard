"""Small reusable field types for request schemas."""

from typing import Annotated

from pydantic import AfterValidator, EmailStr, StringConstraints

# Trimmed, non-empty name
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]

# Valid email, stored lower-case so comparisons are case-insensitive
Email = Annotated[EmailStr, AfterValidator(lambda v: v.strip().lower())]
