"""Live check of the audit trail, /me and patient export against the real API.

Usage (repo root; API_URL and ID_TOKEN exported; optional ID_TOKEN_2 = another doctor's token):
    python3 scripts/test_audit_flow.py
Creates a patient "Audit Test", reads, searches, edits and exports it, then checks that the
doctor's own activity list shows each action, holds no patient values, and that another doctor
cannot see it. Delete the test patient afterwards (see the runbook, "Clean up test data").
"""
import os
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


r = call("GET", "/me")
check("/me returns the caller's email", r.status_code == 200 and "@" in r.json().get("email", ""), r.text)

r = call("POST", "/patients", json={"name": "Audit Test", "age": 33, "contact_number": "5550199"})
check("create patient", r.status_code == 200, r.text)
pid = r.json()["id"]
call("GET", f"/patients/{pid}")
call("GET", "/patients", params={"q": "audit test"})
call("PATCH", f"/patients/{pid}", json={"age": 34})
r = call("GET", f"/patients/{pid}/export")
check("export has patient and a diagnoses list", r.status_code == 200 and r.json()["patient"]["id"] == pid
      and isinstance(r.json()["diagnoses"], list), r.text)

r = call("GET", "/me/activity", params={"limit": 50})
check("activity endpoint works", r.status_code == 200, r.text)
mine = [a for a in r.json() if a.get("patient_id") == pid]
got = {a["action"] for a in mine}
for action in ["patient.create", "patient.view", "patient.update", "patient.export"]:
    check("audit has " + action, action in got, sorted(got))
check("audit has a search event", any(a["action"] == "patient.search" for a in r.json()))
dump = str(r.json()).lower()
check("audit holds no patient values", "audit test" not in dump and "5550199" not in dump)
check("update records field names only",
      any(a["action"] == "patient.update" and a["detail"] == "fields: age" for a in mine), mine)

if H2:
    r2 = call("GET", "/me/activity", headers=H2, params={"limit": 200})
    check("other doctor does not see this activity", r2.status_code == 200 and all(a.get("patient_id") != pid for a in r2.json()))
    check("other doctor cannot export the patient", call("GET", f"/patients/{pid}/export", headers=H2).status_code == 404)

print("\n%s" % ("ALL PASSED" if not failures else "FAILED: " + ", ".join(failures)))
raise SystemExit(1 if failures else 0)
