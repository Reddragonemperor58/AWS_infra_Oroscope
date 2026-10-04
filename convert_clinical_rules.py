"""
One-off: converts the real clinical rules Excel file into a compact JSON
lookup table for rules_engine.py.

Uses an array-of-arrays format (one header row + value rows) instead of a
list of dicts, specifically to avoid repeating ~12 field names across
~592,000 entries. CHECK THE PRINTED FILE SIZE — if it's large, this table
needs to move into Aurora instead of staying a bundled file (reopening
ADR 0005), not be forced to fit regardless.
"""
import json
import os
import openpyxl

SOURCE_FILE = "Final  DD for new software.xlsx"
OUTPUT_FILE = "services/control-plane/app/data/clinical_rules.json"

COLUMN_NAMES = [
    "Ulcer", "Patch", "Growth", "Mucosal Condition", "Sharp Objects",
    "Pigmentation", "Symptoms", "Habits", "Oral Mapping",
    "Provisional Diagnosis", "Differential Diagnosis", "Advise",
]
FIELDS = [c.lower().replace(" ", "_") for c in COLUMN_NAMES]
KEY_FIELD_COUNT = 10  # 9 clinical inputs + Provisional Diagnosis (also an input)

def main():
    wb = openpyxl.load_workbook(SOURCE_FILE, data_only=True, read_only=True)
    ws = wb["For new software"]
    rows = ws.iter_rows(values_only=True)
    header = next(rows)
    idx = {name: header.index(name) for name in COLUMN_NAMES}

    seen = {}
    duplicate_rows = 0
    for r in rows:
        key = tuple(r[idx[c]] for c in COLUMN_NAMES[:KEY_FIELD_COUNT])
        if key in seen:
            duplicate_rows += 1
            continue
        seen[key] = [r[idx[c]] for c in COLUMN_NAMES]

    output = {"fields": FIELDS, "rows": list(seen.values())}

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, separators=(",", ":"))  # no indentation — data file, not for reading

    size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
    print(f"Unique rules written: {len(seen)}")
    print(f"Exact duplicate rows skipped: {duplicate_rows}")
    print(f"Output file size: {size_mb:.1f} MB")
    if size_mb > 100:
        print()
        print("WARNING: combined with FastAPI/SQLAlchemy/boto3/Pydantic, this is at real")
        print("risk of exceeding Lambda's 250MB unzipped package limit. Do not assume this")
        print("still belongs in a bundled file without checking the actual packaged zip size.")

if __name__ == "__main__":
    main()