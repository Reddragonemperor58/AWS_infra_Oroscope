"""Export the allowed values of each clinical_rules input column for the frontend dropdowns.

Usage (repo root, AWS credentials configured):
    python3 scripts/export_clinical_options.py \
        "$(terraform -chdir=infra output -raw aurora_cluster_arn)" \
        "$(terraform -chdir=infra output -raw aurora_secret_arn)"

Writes frontend/options.json and prints a report of values that differ only by case/whitespace
(the nine clinical fields are matched EXACTLY by the lookup, so such duplicates matter).
"""
import json
import pathlib
import sys
import time
from collections import defaultdict

import boto3
from botocore.exceptions import ClientError

if len(sys.argv) != 3:
    sys.exit(__doc__)
cluster_arn, secret_arn = sys.argv[1:3]
COLUMNS = ["ulcer", "patch", "growth", "mucosal_condition", "sharp_objects", "pigmentation",
           "symptoms", "habits", "oral_mapping", "provisional_diagnosis"]
client = boto3.client("rds-data", region_name="ap-south-2")


def distinct(column):
    for attempt in range(8):
        try:
            r = client.execute_statement(
                resourceArn=cluster_arn, secretArn=secret_arn, database="oroscope_aurora",
                sql=f"SELECT DISTINCT {column} FROM clinical_rules ORDER BY 1")
            return [row[0].get("stringValue") for row in r["records"]]
        except ClientError as exc:
            if "resum" in str(exc).lower() and attempt < 7:  # DatabaseResumingException while Aurora wakes up
                print("  database resuming, retrying in 10s...")
                time.sleep(10)
                continue
            raise


options, report = {}, []
for col in COLUMNS:
    values = distinct(col)
    options[col] = values
    groups = defaultdict(list)
    for v in values:
        groups[" ".join((v or "").split()).casefold()].append(v)
    dupes = {k: vs for k, vs in groups.items() if len(vs) > 1}
    print(f"{col:<24} {len(values):>4} distinct values, {len(dupes)} case/whitespace duplicate groups")
    for vs in dupes.values():
        report.append((col, vs))

out = pathlib.Path("frontend")
out.mkdir(exist_ok=True)
(out / "options.json").write_text(json.dumps(options, indent=1, ensure_ascii=False))
print("\nwrote frontend/options.json")
if report:
    print("\nDUPLICATE SPELLINGS (paste this report back):")
    for col, vs in report[:40]:
        print(f"  {col}: {vs!r}")