import uvicorn
from app.main import app
from app.dependencies import get_current_user
from app.models import User
from app.database import SessionLocal

def mock_get_current_user() -> User:
    """Mock user injected for local dev without a real JWT."""
    return User(id="dummy-dev-uuid", email="local@oroscope.app")

# Override the production dependency
app.dependency_overrides[get_current_user] = mock_get_current_user

def seed_mock_user():
    """Ensures the mock user actually exists in the database to satisfy Foreign Keys."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == "dummy-dev-uuid").first()
        if not user:
            print("Seeding dummy-dev-uuid user into the database...")
            db.add(User(id="dummy-dev-uuid", email="local@oroscope.app"))
            db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    seed_mock_user()
    uvicorn.run(app, host="127.0.0.1", port=8000)