from fastapi import Request, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from .database import get_db
from .models import User


def _is_resuming(exc: Exception) -> bool:
    # Aurora Serverless v2 auto-pauses when idle. The first query after a
    # pause raises DatabaseResumingException, wrapped by SQLAlchemy.
    # botocore generates this exception class dynamically per-client, so
    # it can't be imported and caught by type - detect it by name instead.
    root_cause = getattr(exc, "orig", exc)
    return root_cause.__class__.__name__ == "DatabaseResumingException"


def _resuming_error() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail="Database is starting up after a period of inactivity. Please retry in a few seconds.",
        headers={"Retry-After": "5"},
    )


def _find_user(db: Session, cognito_sub: str):
    return db.query(User).filter(User.id == cognito_sub).first()


def _provision_user(db: Session, cognito_sub: str, email: str) -> None:
    """Create the users row for a Cognito identity seen for the first time (ADR 0010).

    ON CONFLICT DO NOTHING makes this safe when two first requests race, and when
    the email already belongs to another row (the caller re-checks afterwards).
    """
    db.execute(
        text("INSERT INTO users (id, email) VALUES (:id, :email) ON CONFLICT DO NOTHING"),
        {"id": cognito_sub, "email": email},
    )
    db.commit()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    aws_event = request.scope.get("aws.event")

    if not aws_event:
        raise HTTPException(status_code=401, detail="Missing AWS API Gateway context")

    try:
        claims = aws_event["requestContext"]["authorizer"]["jwt"]["claims"]
        cognito_sub = claims["sub"]
    except KeyError:
        raise HTTPException(status_code=401, detail="Invalid or missing Cognito claims in authorizer context")

    try:
        user = _find_user(db, cognito_sub)
        if user:
            return user

        # First request from this Cognito user: create their row. API Gateway has already
        # verified the token, and the pool is admin-create-only (ADR 0004), so a valid
        # token can only belong to a doctor an admin created.
        email = (claims.get("email") or "").strip()
        if not email:
            raise HTTPException(
                status_code=401,
                detail="Token has no email claim. Send the Cognito ID token, not the access token.",
            )
        _provision_user(db, cognito_sub, email)
        user = _find_user(db, cognito_sub)
    except HTTPException:
        raise
    except Exception as exc:
        if _is_resuming(exc):
            raise _resuming_error()
        raise  # anything else is a real bug - don't mask it with a friendly message

    if not user:
        # The insert was skipped: this email is already linked to a different Cognito identity.
        raise HTTPException(status_code=409, detail="This email is already registered to a different account.")

    return user
