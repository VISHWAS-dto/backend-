from pydantic import BaseModel, Field, field_validator


def _validate_email(value: str) -> str:
    value = value.strip()
    # Deliberately lightweight: a single "@" with non-empty local and domain
    # parts, and a dot in the domain. Avoids pulling in email-validator.
    local, _, domain = value.partition("@")
    if not local or "@" in domain or "." not in domain or domain.startswith(".") \
            or domain.endswith(".") or " " in value:
        raise ValueError("invalid email address")
    return value.lower()


class SignupRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    name: str = Field(min_length=1)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _validate_email(v)


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _validate_email(v)


class AuthResponse(BaseModel):
    token: str
    tokenType: str = "bearer"
    userId: int
    email: str
    name: str
