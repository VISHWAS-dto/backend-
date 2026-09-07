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


class BusinessRequest(BaseModel):
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    logo_url: str | None = None
    brand_colors: str | None = None


class BusinessResponse(BaseModel):
    id: int
    name: str
    category: str
    logo_url: str | None = None
    brand_colors: str | None = None

    model_config = {"from_attributes": True}


class ProductImageResponse(BaseModel):
    id: int
    image_url: str

    model_config = {"from_attributes": True}


class ProductResponse(BaseModel):
    id: int
    business_id: int
    name: str
    sku: str
    price: float
    description: str | None = None
    images: list[ProductImageResponse] = []

    model_config = {"from_attributes": True}
