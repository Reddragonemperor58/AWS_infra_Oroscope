from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import main, records, support
from app.database import get_db
from app.dependencies import get_current_user


class Db:
    def __init__(self, diagnosis=None):
        self.diagnosis = diagnosis
        self.added, self.commits = [], 0

    def query(self, m):
        return self

    def filter(self, *a):
        return self

    def first(self):
        return self.diagnosis

    def add(self, o):
        self.added.append(o)

    def commit(self):
        self.commits += 1


def client(db):
    app = FastAPI()
    app.include_router(support.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    return TestClient(app)


def test_problem_report_is_stored_audited_and_logged(capsys):
    db = Db()
    r = client(db).post("/problem-reports", json={"message": "  The photo step froze ", "context": "screen=case"})
    assert r.status_code == 200
    report = next(o for o in db.added if type(o).__name__ == "ProblemReport")
    assert report.message == "The photo step froze" and report.doctor_id == "u1"
    assert any(type(o).__name__ == "AuditEvent" and o.action == "report.create" for o in db.added)
    out = capsys.readouterr().out
    assert f"PROBLEM_REPORT id={report.id}" in out
    assert "photo step froze" not in out  # message text never reaches the log
    assert db.commits == 1


@pytest.mark.parametrize("body", [{"message": ""}, {"message": "   "}, {"message": "x" * 2001},
                                  {"message": "ok", "context": "c" * 1001}, {}])
def test_problem_report_rejects_bad_input(body):
    db = Db()
    assert client(db).post("/problem-reports", json=body).status_code == 422
    assert db.added == []


def test_audit_row_does_not_contain_the_message():
    db = Db()
    client(db).post("/problem-reports", json={"message": "Patient Asha Rao crashed it"})
    audit_rows = [o for o in db.added if type(o).__name__ == "AuditEvent"]
    assert "Asha" not in str([vars(o) for o in audit_rows])


def test_dl_upload_url_stores_key_policy_and_audit(monkeypatch):
    seen = []

    class S3:
        def generate_presigned_post(self, **kw):
            seen.append(kw)
            return {"url": "https://s3/x", "fields": {"key": kw["Key"]}}

    diagnosis = SimpleNamespace(id="d1", patient_id="p1", dl_image_s3_key=None)
    db = Db(diagnosis)
    monkeypatch.setattr(main, "IMAGES_BUCKET", "bucket")
    monkeypatch.setattr(main, "get_s3", lambda: S3())
    main.app.dependency_overrides[get_db] = lambda: db
    main.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    try:
        r = TestClient(main.app).post("/diagnoses/d1/dl-upload-url")
    finally:
        main.app.dependency_overrides.clear()
    assert r.status_code == 200
    assert diagnosis.dl_image_s3_key == "diagnoses/d1/dl_image"
    (kw,) = seen
    assert ["content-length-range", 1, main.MAX_IMAGE_BYTES] in kw["Conditions"]
    assert ["starts-with", "$Content-Type", "image/"] in kw["Conditions"]
    assert kw["ExpiresIn"] <= 300
    assert r.json()["image"]["url"] == "https://s3/x"
    assert any(o.action == "diagnosis.dl_upload_url" for o in db.added)


def test_dl_upload_url_for_foreign_diagnosis_is_404(monkeypatch):
    monkeypatch.setattr(main, "IMAGES_BUCKET", "bucket")
    main.app.dependency_overrides[get_db] = lambda: Db(None)
    main.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    try:
        assert TestClient(main.app).post("/diagnoses/dX/dl-upload-url").status_code == 404
    finally:
        main.app.dependency_overrides.clear()
