"""Does PATCH /diagnoses/{id}/clinical-lookup match provisional_diagnosis case/whitespace-insensitively?

Usage (repo root, API_URL and ID_TOKEN exported):
    python3 scripts/test_clinical_lookup.py "FIBROMA"     # the value EXACTLY as stored in clinical_rules

Creates one patient + diagnosis with the standard test inputs, then runs the lookup with several
spellings of the same diagnosis. 200 = matched, 404 = "No matching clinical rule found".
"""
import os
import sys
import time

import requests

if len(sys.argv) != 2:
    sys.exit(__doc__)
stored = sys.argv[1].strip()
API = os.environ["API_URL"].rstrip("/")
H = {"Authorization": f"Bearer {os.environ['ID_TOKEN']}"}


def call(method, path, **kw):
    for _ in range(6):
        r = requests.request(method, API + path, headers=H, timeout=60, **kw)
        if r.status_code != 503:
            return r
        print("  database resuming, retrying in 8s...")
        time.sleep(8)
    return r


patient = call("POST", "/patients", json={"name": "Lookup Test", "age": 40, "gender": "Male", "contact_number": "1"}).json()
d = call("POST", "/diagnoses/clinical-match", json={
    "patient_id": patient["id"], "ulcer": "Round Ulcer", "patch": "White Patch", "growth": "Round Growth",
    "mucosal_condition": "No Abnormality Detected", "sharp_objects": "Not detected",
    "pigmentation": "No Abnormality Detected", "symptoms": "Swelling", "habits": "Tobacco Chewing",
    "oral_mapping": "Retromolar Area"}).json()

variants = [
    ("exact as stored", stored),
    ("UPPER", stored.upper()),
    ("lower", stored.lower()),
    ("Title Case", stored.title()),
    ("leading/trailing spaces", f"  {stored}  "),
]
seen = set()
print(f"\nlookup spellings for stored value {stored!r}:")
for label, value in variants:
    if value in seen:
        continue
    seen.add(value)
    r = call("PATCH", f"/diagnoses/{d['id']}/clinical-lookup", json={"provisional_diagnosis": value})
    body = r.json()
    extra = f"differential={body.get('rules_match_result')!r}" if r.ok else body.get("detail")
    print(f"  {label:<26} {value!r:<34} -> {r.status_code}  {extra}")
print("\nclean up: DELETE FROM patients WHERE name = 'Lookup Test';")