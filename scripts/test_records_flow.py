"""End-to-end check of the record-keeping endpoints against the real API.

Usage (repo root, API_URL and ID_TOKEN exported; optional ID_TOKEN_2 = a different doctor's token):
    python3 scripts/test_records_flow.py

Creates a patient "Records Test", edits it, searches for it, makes a case, then reads the case
history and the case detail. With ID_TOKEN_2 it also proves another doctor gets 404 for all of it.
"""
import os
import sys
import time

import requests

API = os.environ["API_URL"].rstrip("/")
H = {"Authorization": f"Bearer {os.environ['ID_TOKEN']}"}
H2 = {"Authorization": f"Bearer {os.environ['ID_TOKEN_2']}"} if os.environ.get("ID_TOKEN_2") else None
failures = []


def call(method, path, headers=H, **kw):
    for _ in range(6):
        r = requests.request(method, API + path, headers=headers, timeout=60, **kw)
        if r.status_code != 503:
            return r
        print("  database resuming, retrying in 8s...")
        time.sleep(8)
    return r


def check(label, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + label + (" " + str(extra) if extra and not ok else ""))
    if not ok:
        failures.append(label)


r = call("POST", "/patients", json={"name": "Records Test", "age": 31, "gender": "Female", "contact_number": "5550100"})
check("create patient", r.status_code == 200, r.text)
pid = r.json()["id"]

r = call("PATCH", f"/patients/{pid}", json={"name": "Records Test Edited", "age": None})
check("edit patient (name changed, age cleared)",
      r.status_code == 200 and r.json()["name"] == "Records Test Edited" and r.json()["age"] is None, r.text)
check("edit patient: blank name rejected", call("PATCH", f"/patients/{pid}", json={"name": "  "}).status_code == 422)
r = call("GET", f"/patients/{pid}")
check("get patient", r.status_code == 200 and r.json()["gender"] == "Female", r.text)

r = call("GET", "/patients", params={"q": "records test edi", "limit": 5})
check("search by name finds it", r.status_code == 200 and any(p["id"] == pid for p in r.json()), r.text)
r = call("GET", "/patients", params={"q": "5550100"})
check("search by phone finds it", r.status_code == 200 and any(p["id"] == pid for p in r.json()), r.text)
r = call("GET", "/patients", params={"q": "zzz-no-such-patient"})
check("search with no match is empty", r.status_code == 200 and r.json() == [], r.text)
r = call("GET", "/patients", params={"q": "100%"})
check("percent sign is searched literally (no match)", r.status_code == 200 and all(p["id"] != pid for p in r.json()), r.text)
r = call("GET", "/patients", params={"limit": 1})
check("limit=1 returns one patient", r.status_code == 200 and len(r.json()) == 1, r.text)

r = call("POST", "/diagnoses/clinical-match", json={
    "patient_id": pid, "ulcer": "Round Ulcer", "patch": "White Patch", "growth": "Round Growth",
    "mucosal_condition": "No Abnormality Detected", "sharp_objects": "Not detected",
    "pigmentation": "No Abnormality Detected", "symptoms": "Swelling", "habits": "Tobacco Chewing",
    "oral_mapping": "Retromolar Area"})
check("create diagnosis", r.status_code == 200, r.text)
did = r.json()["id"]
r = call("PATCH", f"/diagnoses/{did}/clinical-lookup", json={"provisional_diagnosis": "ORAL LEUKOPLAKIA"})
check("clinical lookup", r.status_code == 200, r.text)

r = call("GET", f"/patients/{pid}/diagnoses")
check("history lists the case", r.status_code == 200 and [d["id"] for d in r.json()] == [did], r.text)
check("history shows the provisional diagnosis that was looked up",
      r.status_code == 200 and r.json()[0].get("provisional_diagnosis") == "ORAL LEUKOPLAKIA", r.text)

r = call("GET", f"/diagnoses/{did}")
d = r.json() if r.status_code == 200 else {}
check("detail has findings and advice",
      r.status_code == 200 and d.get("symptoms") == "Swelling" and d.get("mucosal_condition") == "No Abnormality Detected"
      and d.get("rules_match_result") and d.get("advise"), r.text)
check("detail has no photo links before any upload (keys not issued yet)", d.get("image_1_url") is None, d)

up = call("POST", f"/diagnoses/{did}/optical-upload-urls")
check("issue upload urls", up.status_code == 200, up.text)
r = call("GET", f"/diagnoses/{did}")
d = r.json()
check("detail now has two signed photo links", bool(d.get("image_1_url")) and bool(d.get("image_2_url")), d)
if d.get("image_1_url"):
    check("signed link points at the regional S3 endpoint", "s3.ap-south-2.amazonaws.com" in d["image_1_url"], d["image_1_url"])

check("unknown ids return 404",
      call("GET", "/patients/does-not-exist").status_code == 404
      and call("GET", "/diagnoses/does-not-exist").status_code == 404
      and call("GET", "/patients/does-not-exist/diagnoses").status_code == 404)

if H2:
    check("other doctor: patient 404", call("GET", f"/patients/{pid}", headers=H2).status_code == 404)
    check("other doctor: edit 404", call("PATCH", f"/patients/{pid}", headers=H2, json={"name": "X"}).status_code == 404)
    check("other doctor: history 404", call("GET", f"/patients/{pid}/diagnoses", headers=H2).status_code == 404)
    check("other doctor: diagnosis 404", call("GET", f"/diagnoses/{did}", headers=H2).status_code == 404)
    r = call("GET", "/patients", headers=H2, params={"q": "Records Test"})
    check("other doctor: search does not list it", r.status_code == 200 and all(p["id"] != pid for p in r.json()), r.text)
else:
    print("SKIP other-doctor checks (set ID_TOKEN_2 to a different doctor's ID token)")

print("\nCleanup: DELETE FROM patients WHERE name LIKE 'Records Test%';")
sys.exit(1 if failures else 0)
