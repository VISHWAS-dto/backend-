from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models  # noqa: F401  (ensures models are registered on Base.metadata)
from app.auth import create_access_token, hash_password, verify_password
from app.database import Base, engine, get_db
from app.dependencies import get_current_user
from app.products import router as products_router
from app.schemas import (
    AuthResponse,
    BusinessRequest,
    BusinessResponse,
    LoginRequest,
    SignupRequest,
)

# Create any missing tables on startup.
Base.metadata.create_all(bind=engine)


def _ensure_product_image_validation_columns() -> None:
    """Add the Phase 6 validation columns to product_images if they're missing.

    create_all() won't alter an existing table, so for databases created before
    Phase 6 we add the columns here. Both statements are no-ops on an
    already-migrated database.
    """
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE product_images "
                "ADD COLUMN IF NOT EXISTS validation_status VARCHAR"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE product_images "
                "ADD COLUMN IF NOT EXISTS validation_reasons TEXT"
            )
        )


_ensure_product_image_validation_columns()

app = FastAPI(title="catalyx-backend-py")

# Serve uploaded files (e.g. product images) from the local "uploads" directory.
_UPLOADS_DIR = Path("uploads")
_UPLOADS_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=_UPLOADS_DIR), name="uploads")

app.include_router(products_router)


@app.exception_handler(RequestValidationError)
def validation_exception_handler(request, exc: RequestValidationError):
    """Return a compact JSON list of field errors instead of the default payload."""
    errors = [
        {
            "field": ".".join(str(p) for p in err["loc"] if p != "body"),
            "message": err["msg"],
        }
        for err in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": "Validation failed", "errors": errors})


@app.get("/")
def health_check():
    return {"status": "ok", "message": "catalyx-backend-py is running"}


def _auth_response(user: models.User) -> AuthResponse:
    token = create_access_token({"sub": str(user.id), "email": user.email})
    return AuthResponse(
        token=token,
        tokenType="bearer",
        userId=user.id,
        email=user.email,
        name=user.name,
    )


@app.post("/signup", response_model=AuthResponse, status_code=201)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    if len(payload.password) < 8:
        return JSONResponse(
            status_code=422,
            content={"detail": "Password must be at least 8 characters long"},
        )

    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing is not None:
        return JSONResponse(
            status_code=409,
            content={"detail": "An account with this email already exists"},
        )

    user = models.User(
        email=payload.email,
        password=hash_password(payload.password),
        name=payload.name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return _auth_response(user)


@app.post("/business", response_model=BusinessResponse, status_code=201)
def create_business(
    payload: BusinessRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a business owned by the authenticated user."""
    business = models.Business(
        user_id=current_user.id,
        name=payload.name,
        category=payload.category,
        logo_url=payload.logo_url,
        brand_colors=payload.brand_colors,
    )
    db.add(business)
    db.commit()
    db.refresh(business)
    return business


@app.get("/business", response_model=BusinessResponse)
def get_business(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the authenticated user's own business, or 404 if they have none."""
    business = (
        db.query(models.Business)
        .filter(models.Business.user_id == current_user.id)
        .first()
    )
    if business is None:
        return JSONResponse(
            status_code=404,
            content={"detail": "No business found for this account"},
        )
    return business


@app.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.password):
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid email or password"},
        )

    return _auth_response(user)
