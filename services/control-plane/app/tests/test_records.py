from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import records
from app.database import get_db
from app.dependencies import get_current_user

NOW = datetime(2026, 10, 22, 12, 0, 0)


class FakeQuery:
    """Chainable stand-in for a SQLAlchemy query: every filter step returns itself."""
    def __init__(self, rows, filters=None):
        self.rows = rows
        self.filters = filters if filters is not None else []

    def __getattr__(self, name):
        if name == "filter":
            def keep(*conditions, **k):
                self.filters.extend(conditions)
                return self
            return keep
        if name in ("order_by", "offset", "limit"):
            return lambda *a, **k: self
        raise AttributeError(name)

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class FakeDb:
    def __init__(self, patients=(), diagnoses=(), events=()):
        self.data = {"Patient": list(patients), "Diagnosis": list(diagnoses), "AuditEvent": list(events)}
        self.added = []
        self.commits = 0
        self.filters = []

    def query(self, model):
        return FakeQuery(self.data[model.__name__], self.filters)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        # the real refresh reloads the row, turning updated_at = now() into a timestamp
        if hasattr(obj, "updated_at") and not isinstance(obj.updated_at, datetime):
            obj.updated_at = NOW


def make_patient(**kw):
    base = dict(id="p1", doctor_id="u1", name="Asha", age=40, gender="Female",
                contact_number="999", created_at=NOW, updated_at=NOW)
    base.update(kw)
    return SimpleNamespace(**base)


def make_diagnosis(**kw):
    base = dict(
        id="d1", patient_id="p1", doctor_id="u1", status=SimpleNamespace(value="complete"),
        created_at=NOW, updated_at=NOW, provisional_diagnosis="FIBROMA",
        ulcer="Round Ulcer", patch="White Patch", growth="Round Growth", mucosal_type="No Abnormality Detected",
        sharp_objects="Not detected", pigmentation="No Abnormality Detected", symptoms="Swelling",
        habits="Tobacco Chewing", oral_mapping="Retromolar Area", rules_match_result="FIBROMA, APTHOUS ULCER",
        advise="Follow up", optical_deviation_index=0.25, final_score=3,
        optical_image_1_s3_key="diagnoses/d1/optical_1", optical_image_2_s3_key=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def client(db):
    app = FastAPI()
    app.include_router(records.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    return TestClient(app)


@pytest.fixture(autouse=True)
def no_s3(monkeypatch):
    monkeypatch.setattr(records, "_photo_link", lambda key: ("https://signed/" + key) if key else None)


def test_search_sql_has_no_backslash_or_escape_clause():
    """The RDS Data API's SQL parser breaks on ESCAPE '\\' (it hides the next parameter), which
    caused a 500 in production. Search must compile to SQL with neither."""
    from sqlalchemy.dialects import postgresql

    db = FakeDb(patients=[make_patient()])
    assert client(db).get("/patients", params={"q": "50%_a\\b"}).status_code == 200
    sql = " ".join(str(f.compile(dialect=postgresql.dialect())) for f in db.filters)
    assert "ESCAPE" not in sql.upper() and "\\" not in sql and "LIKE" not in sql.upper()
    assert "strpos" in sql


def test_list_patients_returns_patients():
    r = client(FakeDb(patients=[make_patient()])).get("/patients?q=as&limit=10&offset=0")
    assert r.status_code == 200 and r.json()[0]["name"] == "Asha"


@pytest.mark.parametrize("qs", ["limit=0", "limit=201", "offset=-1", "q=" + "x" * 101])
def test_list_patients_rejects_bad_params(qs):
    assert client(FakeDb()).get("/patients?" + qs).status_code == 422


def test_get_patient_404_when_not_owned_or_missing():
    assert client(FakeDb()).get("/patients/nope").status_code == 404


def test_update_patient_changes_only_sent_fields():
    p = make_patient()
    db = FakeDb(patients=[p])
    r = client(db).patch("/patients/p1", json={"age": None, "name": "  Asha Rao "})
    assert r.status_code == 200
    assert p.name == "Asha Rao" and p.age is None and p.gender == "Female"
    assert db.commits == 1


def test_update_patient_rejects_blank_name_and_bad_age():
    c = client(FakeDb(patients=[make_patient()]))
    assert c.patch("/patients/p1", json={"name": "   "}).status_code == 422
    assert c.patch("/patients/p1", json={"age": 200}).status_code == 422


def test_update_missing_patient_is_404():
    assert client(FakeDb()).patch("/patients/x", json={"name": "A"}).status_code == 404


def test_history_lists_cases_with_band_and_score():
    db = FakeDb(patients=[make_patient()], diagnoses=[make_diagnosis()])
    r = client(db).get("/patients/p1/diagnoses")
    assert r.status_code == 200
    row = r.json()[0]
    assert row["image_analysis_band"] == "Suggestive of Dysplasia" and row["final_score"] == 3.0
    assert row["provisional_diagnosis"] == "FIBROMA"


def test_history_of_foreign_patient_is_404():
    assert client(FakeDb(diagnoses=[make_diagnosis()])).get("/patients/p9/diagnoses").status_code == 404


def test_diagnosis_detail_has_findings_and_photo_links():
    r = client(FakeDb(diagnoses=[make_diagnosis()])).get("/diagnoses/d1")
    assert r.status_code == 200
    body = r.json()
    assert body["mucosal_condition"] == "No Abnormality Detected" and body["symptoms"] == "Swelling"
    assert body["image_1_url"] == "https://signed/diagnoses/d1/optical_1" and body["image_2_url"] is None


def test_unanalysed_case_has_no_band_or_score():
    d = make_diagnosis(optical_deviation_index=None, final_score=None, provisional_diagnosis=None,
                       status=SimpleNamespace(value="pending"))
    body = client(FakeDb(diagnoses=[d])).get("/diagnoses/d1").json()
    assert body["image_analysis_band"] is None and body["final_score"] is None and body["status"] == "pending"


def test_missing_diagnosis_is_404():
    assert client(FakeDb()).get("/diagnoses/x").status_code == 404


# ---- audit trail, /me, export ----
def actions(db):
    return [e.action for e in db.added]


def test_reads_write_an_audit_row_and_commit():
    db = FakeDb(patients=[make_patient()], diagnoses=[make_diagnosis()])
    c = client(db)
    c.get("/patients")
    c.get("/patients", params={"q": "asha"})
    c.get("/patients/p1")
    c.get("/patients/p1/diagnoses")
    c.get("/diagnoses/d1")
    assert actions(db) == ["patient.list", "patient.search", "patient.view", "diagnosis.list", "diagnosis.view"]
    assert db.commits == 5
    assert all(e.doctor_id == "u1" for e in db.added)


def test_audit_never_stores_the_search_text_or_patient_values():
    db = FakeDb(patients=[make_patient()])
    client(db).get("/patients", params={"q": "9876543210"})
    dump = " ".join(str(vars(e)) for e in db.added)
    assert "9876543210" not in dump and "Asha" not in dump


def test_update_audit_lists_field_names_only():
    db = FakeDb(patients=[make_patient()])
    client(db).patch("/patients/p1", json={"name": "New Name", "age": 41})
    (event,) = db.added
    assert event.action == "patient.update" and event.detail == "fields: age,name"
    assert "New Name" not in str(vars(event))


def test_failed_lookup_writes_no_audit_row():
    db = FakeDb()
    assert client(db).get("/patients/nope").status_code == 404
    assert db.added == []


def test_me_returns_the_caller(monkeypatch):
    app = FastAPI()
    app.include_router(records.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1", email="a@b.com", created_at=NOW)
    r = TestClient(app).get("/me")
    assert r.status_code == 200 and r.json()["email"] == "a@b.com"


def test_activity_is_filtered_to_the_caller():
    from sqlalchemy.dialects import postgresql
    ev = SimpleNamespace(action="patient.view", resource_type="patient", resource_id="p1",
                         patient_id="p1", detail=None, created_at=NOW)
    db = FakeDb(events=[ev])
    r = client(db).get("/me/activity")
    assert r.status_code == 200 and r.json()[0]["action"] == "patient.view"
    sql = " ".join(str(f.compile(dialect=postgresql.dialect())) for f in db.filters)
    assert "doctor_id" in sql


def test_export_has_patient_and_cases_and_is_audited():
    db = FakeDb(patients=[make_patient()], diagnoses=[make_diagnosis()])
    r = client(db).get("/patients/p1/export")
    body = r.json()
    assert r.status_code == 200
    assert body["patient"]["name"] == "Asha" and body["diagnoses"][0]["id"] == "d1"
    assert body["diagnoses"][0]["image_1_url"].startswith("https://signed/")
    assert actions(db) == ["patient.export"]


def test_export_of_foreign_patient_is_404():
    assert client(FakeDb()).get("/patients/p9/export").status_code == 404


def test_detail_includes_dl_photo_link_when_present():
    db = FakeDb(diagnoses=[make_diagnosis(dl_image_s3_key="diagnoses/d1/dl_image")])
    body = client(db).get("/diagnoses/d1").json()
    assert body["dl_image_url"] == "https://signed/diagnoses/d1/dl_image"


def test_detail_dl_photo_link_is_null_when_absent():
    db = FakeDb(diagnoses=[make_diagnosis()])
    assert client(db).get("/diagnoses/d1").json()["dl_image_url"] is None
