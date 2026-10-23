"""Importing app.main is the one thing the Lambda does at cold start. If a bad import or a
missing include_router slips in, every other test can still pass while the deployed function
crashes. This test fails first."""

EXPECTED = {
    "/health": {"get"},
    "/patients": {"get", "post"},
    "/patients/{patient_id}": {"get", "patch"},
    "/patients/{patient_id}/diagnoses": {"get"},
    "/diagnoses/clinical-match": {"post"},
    "/diagnoses/{diagnosis_id}": {"get"},
    "/diagnoses/{diagnosis_id}/clinical-lookup": {"patch"},
    "/diagnoses/{diagnosis_id}/optical-upload-urls": {"post"},
    "/diagnoses/{diagnosis_id}/optical": {"patch"},
}


def test_app_imports_and_exposes_every_route():
    from app import main  # fails here on a bad import

    paths = main.app.openapi()["paths"]
    actual = {path: set(ops) for path, ops in paths.items()}
    assert actual == EXPECTED


def test_each_path_and_method_is_registered_once():
    from app import main

    seen = []
    for path, ops in main.app.openapi()["paths"].items():
        seen += [(path, method) for method in ops]
    assert len(seen) == len(set(seen))
