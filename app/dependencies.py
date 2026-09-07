from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app import models
from app.auth import decode_access_token
from app.database import get_db

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> models.User:
    """Resolve the ``Authorization: Bearer <token>`` header to a ``User``.

    Raises 401 with a specific message when the header is missing, not a Bearer
    token, the JWT fails to validate/expires, or the user it names no longer
    exists.
    """
    if authorization is None:
        raise _unauthorized("Authorization header is missing")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise _unauthorized(
            "Authorization header must be in the form 'Bearer <token>'"
        )

    claims = decode_access_token(token.strip())
    if claims is None:
        raise _unauthorized("Token is invalid or has expired")

    subject = claims.get("sub")
    if subject is None:
        raise _unauthorized("Token is missing the subject claim")

    try:
        user_id = int(subject)
    except (TypeError, ValueError):
        raise _unauthorized("Token subject is malformed")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise _unauthorized("Token refers to a user that no longer exists")

    return user
