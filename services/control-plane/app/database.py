import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
DATABASE_URL = ("postgresql+auroradataapi://:@/oroscope_aurora"
  f"?aurora_cluster_arn={os.environ.get('AURORA_CLUSTER_ARN', '')}&secret_arn={os.environ.get('AURORA_SECRET_ARN', '')}")
engine = create_engine(DATABASE_URL, hide_parameters=True)  # keep patient values out of error logs
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
