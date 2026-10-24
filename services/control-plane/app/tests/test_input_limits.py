"""Oversized or blank input must be rejected at the edge (422), before it reaches the database."""
import pytest
from pydantic import ValidationError


def test_patient_create_accepts_normal_and_strips_name():
    from app.main import PatientCreate
    p = PatientCreate(name="  Asha Rao ", age=45, gender="F", contact_number="9876543210")
    assert p.name == "Asha Rao"


@pytest.mark.parametrize("bad", [
    {"name": ""}, {"name": "   "}, {"name": "x" * 101},
    {"name": "a", "age": -1}, {"name": "a", "age": 121},
    {"name": "a", "gender": "g" * 21}, {"name": "a", "contact_number": "1" * 21},
])
def test_patient_create_rejects_bad_input(bad):
    from app.main import PatientCreate
    with pytest.raises(ValidationError):
        PatientCreate(**bad)


def test_clinical_request_rejects_oversized_field():
    from app.main import ClinicalMatchRequest
    ok = {k: "x" for k in ["ulcer", "patch", "growth", "mucosal_condition", "sharp_objects",
                           "pigmentation", "symptoms", "habits", "oral_mapping"]}
    ClinicalMatchRequest(patient_id="p", **ok)
    with pytest.raises(ValidationError):
        ClinicalMatchRequest(patient_id="p", **{**ok, "ulcer": "x" * 256})
    with pytest.raises(ValidationError):
        ClinicalMatchRequest(patient_id="p" * 37, **ok)


def test_response_model_does_not_reject_stored_data():
    from app.main import PatientResponse
    assert "max_length" not in str(PatientResponse.model_fields["name"])


def test_engine_hides_sql_parameters():
    from app import database
    assert database.engine.hide_parameters is True
