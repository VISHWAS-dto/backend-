"""Routes for AI catalogue-generation jobs.

``POST /generate`` kicks off a generation for one product and records the
outcome as an :class:`~app.models.AiJob`. ``GET /status/{job_id}`` reports where
that job got to. Both are scoped to the authenticated user's own business.

The AI call itself lives in :mod:`app.ai_service`; this module only orchestrates
the job record and translates an :class:`~app.ai_service.AiServiceError` into a
``FAILED`` job (never a 500).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models
from app.ai_service import AiServiceError, generate_catalogue_content
from app.database import get_db
from app.dependencies import get_current_user
from app.schemas import AiJobResponse, GenerateRequest

router = APIRouter(tags=["ai"])

# AiJob.status values used by these routes.
STATUS_PROCESSING = "PROCESSING"
STATUS_DONE = "DONE"
STATUS_FAILED = "FAILED"


def _product_for_user(
    product_id: int, user: models.User, db: Session
) -> models.Product:
    """Return the product if it belongs to the user's business, else raise 404."""
    product = (
        db.query(models.Product)
        .join(models.Business, models.Product.business_id == models.Business.id)
        .filter(
            models.Product.id == product_id,
            models.Business.user_id == user.id,
        )
        .first()
    )
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found for this account",
        )
    return product


@router.post("/generate", response_model=AiJobResponse, status_code=status.HTTP_201_CREATED)
def generate_catalogue(
    payload: GenerateRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate catalogue content for a product and record the job outcome.

    Always creates an :class:`~app.models.AiJob`: it starts as ``PROCESSING``,
    then becomes ``DONE`` with the generated text, or ``FAILED`` with the error
    message if the AI call raises. An AI failure never propagates as a 5xx.
    """
    product = _product_for_user(payload.product_id, current_user, db)

    job = models.AiJob(product_id=product.id, status=STATUS_PROCESSING)
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        content = generate_catalogue_content(product.name, product.description)
    except AiServiceError as exc:
        job.status = STATUS_FAILED
        job.result = str(exc)
    except Exception as exc:  # noqa: BLE001 - defensive: never crash the request
        job.status = STATUS_FAILED
        job.result = f"Unexpected error during generation: {exc}"
    else:
        job.status = STATUS_DONE
        job.result = content

    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("/status/{job_id}", response_model=AiJobResponse)
def get_job_status(
    job_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current status and result of an AI job owned by the user."""
    job = (
        db.query(models.AiJob)
        .join(models.Product, models.AiJob.product_id == models.Product.id)
        .join(models.Business, models.Product.business_id == models.Business.id)
        .filter(
            models.AiJob.id == job_id,
            models.Business.user_id == current_user.id,
        )
        .first()
    )
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI job not found for this account",
        )
    return job
