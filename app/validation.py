"""Deterministic, pre-AI image quality checks for product uploads.

Every uploaded product image is run through :func:`validate_image` before it is
handed off to the (later) AI generation step. The checks here are intentionally
simple and reproducible — no model calls, just resolution and sharpness math —
so the same file always produces the same verdict.
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError

# An image must be at least this many pixels on each side. Anything smaller
# tends to look soft or pixelated once placed into a generated catalogue layout.
MIN_WIDTH = 400
MIN_HEIGHT = 400

# Variance of the Laplacian is a standard, cheap focus measure: a sharp image
# has lots of high-frequency edge energy (high variance); a blurry one is smooth
# (low variance). The absolute number depends on image size and content, so this
# threshold is a pragmatic middle-ground rather than a hard rule.
BLUR_VARIANCE_THRESHOLD = 100.0

STATUS_READY = "READY_FOR_AI_GENERATION"
STATUS_NEEDS_ATTENTION = "NEEDS_ATTENTION"


def _laplacian_variance(gray: "np.ndarray") -> float:
    """Return the variance of the Laplacian of a single-channel image."""
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def validate_image(filepath: str) -> dict:
    """Run deterministic quality checks on the image at ``filepath``.

    Returns a dict shaped like::

        {
            "status": "READY_FOR_AI_GENERATION" | "NEEDS_ATTENTION",
            "reasons": ["...", ...],   # empty when status is READY
            "metrics": {"width": int, "height": int, "laplacian_variance": float},
        }

    The function never raises for a bad/corrupt image — it reports that as a
    ``NEEDS_ATTENTION`` reason instead, so a single bad file can't break an
    otherwise valid multi-image upload.
    """
    reasons: list[str] = []
    metrics: dict = {"width": None, "height": None, "laplacian_variance": None}

    # --- Resolution check (Pillow) -------------------------------------------
    try:
        with Image.open(filepath) as img:
            img.verify()  # cheap integrity check; invalidates the handle
        with Image.open(filepath) as img:
            width, height = img.size
    except (UnidentifiedImageError, OSError, ValueError):
        return {
            "status": STATUS_NEEDS_ATTENTION,
            "reasons": ["Image could not be read or is corrupt."],
            "metrics": metrics,
        }

    metrics["width"] = width
    metrics["height"] = height

    if width < MIN_WIDTH or height < MIN_HEIGHT:
        reasons.append(
            f"Resolution {width}x{height} is below the minimum "
            f"{MIN_WIDTH}x{MIN_HEIGHT}."
        )

    # --- Blur / sharpness check (OpenCV Laplacian variance) -----------------
    image = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
    if image is None:
        reasons.append("Image could not be decoded for sharpness analysis.")
    else:
        variance = _laplacian_variance(image)
        metrics["laplacian_variance"] = round(variance, 2)
        if variance < BLUR_VARIANCE_THRESHOLD:
            reasons.append(
                f"Image appears blurry (sharpness score {variance:.1f} is below "
                f"the {BLUR_VARIANCE_THRESHOLD:.0f} threshold)."
            )

    status = STATUS_NEEDS_ATTENTION if reasons else STATUS_READY
    return {"status": status, "reasons": reasons, "metrics": metrics}
