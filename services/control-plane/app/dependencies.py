from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .database import get_db
from .models import User

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Extracts the Cognito 'sub' verified by API Gateway."""
    aws_event = request.scope.get("aws.event")
    
    if not aws_event:
        # No escape hatch here. If it's not from AWS, it fails.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing AWS API Gateway context"
        )
        
    try:
        cognito_sub = aws_event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Cognito claims in authorizer context"
        )
        
    user = db.query(User).filter(User.id == cognito_sub).first()
    if not user:
        raise HTTPException(status_code=401, detail="User identity verified, but missing from database.")
        
    return user