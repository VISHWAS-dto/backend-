import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.dependencies import get_current_user
from app.schemas import ProductResponse
from app.validation import validate_image

router = APIRouter(prefix="/products", tags=["products"])

# Where uploaded product images land on disk. Served publicly via the
# "/uploads" static mount configured in app.main.
UPLOAD_ROOT = Path("uploads/products")

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

# Accepted image types, keyed by the content type the client sends. The value is
# the extension we store the file under.
_ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
}
_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def _bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


def _extension_for(image: UploadFile) -> str:
    """Return the on-disk extension for an upload, or raise a 400 if unsupported.

    Validates both the declared content type and the filename extension so a
    mislabelled upload is still rejected.
    """
    content_type = (image.content_type or "").lower()
    suffix = Path(image.filename or "").suffix.lower()

    if content_type not in _ALLOWED_TYPES or suffix not in _ALLOWED_EXTENSIONS:
        raise _bad_request(
            f"'{image.filename}' is not an accepted image. Only JPG and PNG files "
            "are allowed."
        )
    return _ALLOWED_TYPES[content_type]


def _read_within_limit(image: UploadFile) -> bytes:
    """Read an upload fully, raising a 400 if it exceeds MAX_FILE_SIZE."""
    contents = image.file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise _bad_request(
            f"'{image.filename}' is {len(contents) / (1024 * 1024):.1f} MB, which "
            "exceeds the 5 MB limit."
        )
    if not contents:
        raise _bad_request(f"'{image.filename}' is empty.")
    return contents


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    request: Request,
    name: str = Form(..., min_length=1),
    sku: str = Form(..., min_length=1),
    price: float = Form(..., gt=0),
    description: str | None = Form(None),
    images: list[UploadFile] = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a product for the authenticated user's business with image uploads."""
    business = (
        db.query(models.Business)
        .filter(models.Business.user_id == current_user.id)
        .first()
    )
    if business is None:
        raise _bad_request(
            "You must create a business before adding products."
        )

    if not images or all(not img.filename for img in images):
        raise _bad_request("At least one image file is required.")

    # Validate every file up front so we don't persist a product with a
    # half-written set of images.
    validated: list[tuple[bytes, str]] = []
    for image in images:
        extension = _extension_for(image)
        contents = _read_within_limit(image)
        validated.append((contents, extension))

    product = models.Product(
        business_id=business.id,
        name=name,
        sku=sku,
        price=price,
        description=description,
    )
    db.add(product)
    db.flush()  # assign product.id without committing yet

    dest_dir = UPLOAD_ROOT / str(product.id)
    dest_dir.mkdir(parents=True, exist_ok=True)

    base_url = str(request.base_url).rstrip("/")
    for contents, extension in validated:
        filename = f"{uuid.uuid4().hex}{extension}"
        file_path = dest_dir / filename
        file_path.write_bytes(contents)

        # Deterministic pre-AI quality gate (resolution + blur). Runs on the
        # file we just wrote; the result is stored alongside the image.
        result = validate_image(str(file_path))

        relative_url = f"/uploads/products/{product.id}/{filename}"
        db.add(
            models.ProductImage(
                product_id=product.id,
                image_url=f"{base_url}{relative_url}",
                validation_status=result["status"],
                validation_reasons="\n".join(result["reasons"]),
            )
        )

    db.commit()
    db.refresh(product)
    return product


@router.get("", response_model=list[ProductResponse])
def list_products(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all products for the authenticated user's business."""
    business = (
        db.query(models.Business)
        .filter(models.Business.user_id == current_user.id)
        .first()
    )
    if business is None:
        return []

    return (
        db.query(models.Product)
        .filter(models.Product.business_id == business.id)
        .order_by(models.Product.created_at.desc())
        .all()
    )
