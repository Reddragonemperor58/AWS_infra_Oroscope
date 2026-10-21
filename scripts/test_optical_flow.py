"""End-to-end test of the optical flow against the LIVE API.

Usage (from repo root, venv active):
    pip install requests pillow numpy
    export API_URL="https://jy3bq91s6k.execute-api.ap-south-2.amazonaws.com"
    export ID_TOKEN="<Cognito IdToken from test_login.py>"
    python scripts/test_optical_flow.py red.jpg blue.jpg "Fibroma"

Steps: create patient -> clinical-match -> request upload URLs -> upload both images to S3
-> PATCH optical -> compare the API's SSIM with a local calculation from the same files.
"""
import importlib.util
import os
import sys

import requests

if len(sys.argv) != 4:
    sys.exit(__doc__)
img1_path, img2_path, provisional = sys.argv[1:4]
API = os.environ["API_URL"].rstrip("/")
H = {"Authorization": f"Bearer {os.environ['ID_TOKEN']}"}


def call(method, path, **kw):
    for attempt in range(6):  # Aurora may be auto-paused: API returns 503 + Retry-After while it resumes
        r = requests.request(method, API + path, headers=H, timeout=60, **kw)
        if r.status_code != 503:
            break
        print("  database resuming, retrying in 8s...")
        import time; time.sleep(8)
    print(f"{method} {path} -> {r.status_code}")
    if not r.ok:
        sys.exit(r.text)
    return r.json()


patient = call("POST", "/patients", json={"name": "Optical Test", "age": 40, "gender": "Male", "contact_number": "1234567890"})
diag = call("POST", "/diagnoses/clinical-match", json={
    "patient_id": patient["id"], "ulcer": "Round Ulcer", "patch": "White Patch", "growth": "Round Growth",
    "mucosal_condition": "No Abnormality Detected", "sharp_objects": "Not detected",
    "pigmentation": "No Abnormality Detected", "symptoms": "Swelling", "habits": "Tobacco Chewing",
    "oral_mapping": "Retromolar Area"})
did = diag["id"]

urls = call("POST", f"/diagnoses/{did}/optical-upload-urls")
for target, path in ((urls["image_1"], img1_path), (urls["image_2"], img2_path)):
    ctype = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    with open(path, "rb") as f:
        # S3 POST: all policy fields (+ Content-Type) first, the file part LAST.
        r = requests.post(target["url"], data={**target["fields"], "Content-Type": ctype}, files={"file": f}, timeout=120)
    print(f"S3 upload {os.path.basename(path)} -> {r.status_code}")
    if r.status_code not in (200, 201, 204):
        sys.exit(r.text)

res = call("PATCH", f"/diagnoses/{did}/optical", json={"provisional_diagnosis": provisional})
for k in ("provisional_diagnosis", "ssim_score", "optical_deviation_index", "image_analysis_band", "final_score", "resized", "status", "warning"):
    print(f"  {k}: {res.get(k)}")

# Independent check: recompute SSIM locally from the same two files with the same module.
try:
    from pathlib import Path
    optical_path = Path(__file__).resolve().parent.parent / "services" / "control-plane" / "app" / "optical.py"
    spec = importlib.util.spec_from_file_location("optical", optical_path)
    optical = importlib.util.module_from_spec(spec); spec.loader.exec_module(optical)
    local = optical.calculate_ssim(open(img1_path, "rb").read(), open(img2_path, "rb").read())["ssim_score"]
    ok = abs(local - res["ssim_score"]) < 1e-9
    print(f"local SSIM {local:.9f} vs API {res['ssim_score']:.9f} -> {'MATCH' if ok else 'MISMATCH'}")
except Exception as exc:
    print("local comparison skipped:", exc)