import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Use the exact, proven URL pattern with query parameters
DATABASE_URL = (
    f"postgresql+auroradataapi://:@/oroscope_aurora"
    f"?aurora_cluster_arn={os.environ.get('AURORA_CLUSTER_ARN', '')}"
    f"&secret_arn={os.environ.get('AURORA_SECRET_ARN', '')}"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()