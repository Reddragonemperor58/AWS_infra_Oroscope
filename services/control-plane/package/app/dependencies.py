from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .database import get_db
from .models import User

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    aws_event = request.scope.get("aws.event")

    if not aws_event:
        raise HTTPException(status_code=401, detail="Missing AWS API Gateway context")

    try:
        cognito_sub = aws_event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
    except KeyError:
        raise HTTPException(status_code=401, detail="Invalid or missing Cognito claims in authorizer context")

    try:
        user = db.query(User).filter(User.id == cognito_sub).first()
    except Exception as exc:
        # Aurora Serverless v2 auto-pauses when idle. The first query after a
        # pause raises DatabaseResumingException, wrapped by SQLAlchemy.
        # botocore generates this exception class dynamically per-client, so
        # it can't be imported and caught by type — detect it by name instead.
        root_cause = getattr(exc, "orig", exc)
        if root_cause.__class__.__name__ == "DatabaseResumingException":
            raise HTTPException(
                status_code=503,
                detail="Database is starting up after a period of inactivity. Please retry in a few seconds.",
                headers={"Retry-After": "5"},
            )
        raise  # anything else is a real bug — don't mask it with a friendly message

    if not user:
        raise HTTPException(status_code=401, detail="User identity verified, but missing from database.")

    return user