"""The presigned POST is the only gate in front of S3 for uploads: pin its conditions."""
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import main
from app.database import get_db
from app.dependencies import get_current_user


def test_upload_policy_limits_size_and_type(monkeypatch):
    seen = []

    class S3:
        def generate_presigned_post(self, **kw):
            seen.append(kw)
            return {"url": "https://s3/x", "fields": {}}

    class Db:
        def query(self, m):
            return self
        def filter(self, *a):
            return self
        def first(self):
            return SimpleNamespace(id="d1", patient_id="p1", optical_image_1_s3_key=None, optical_image_2_s3_key=None)
        def add(self, o): pass
        def commit(self): pass

    monkeypatch.setattr(main, "IMAGES_BUCKET", "bucket")
    monkeypatch.setattr(main, "get_s3", lambda: S3())
    main.app.dependency_overrides[get_db] = lambda: Db()
    main.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    try:
        r = TestClient(main.app).post("/diagnoses/d1/optical-upload-urls")
    finally:
        main.app.dependency_overrides.clear()
    assert r.status_code == 200
    assert len(seen) == 2
    for kw in seen:
        assert ["content-length-range", 1, main.MAX_IMAGE_BYTES] in kw["Conditions"]
        assert ["starts-with", "$Content-Type", "image/"] in kw["Conditions"]
        assert kw["ExpiresIn"] <= 300
        assert kw["Key"].startswith("diagnoses/d1/")
