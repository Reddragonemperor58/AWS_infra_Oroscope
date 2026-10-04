"""
One-time bulk load of clinical_rules into Aurora. Not an Alembic migration —
this is data, not schema. Safe to re-run against an empty table; will fail
loudly on the unique index if run twice without truncating first.
"""
import json
import time
import openpyxl
import boto3

SOURCE_FILE = "Final  DD for new software.xlsx"
CLUSTER_ARN = "arn:aws:rds:ap-south-2:663476173766:cluster:oroscope-dev-aurora-cluster"
SECRET_ARN = "arn:aws:secretsmanager:ap-south-2:663476173766:secret:rds!cluster-34b75af6-5d80-4881-91e6-2406c3614b9d-0FbC9F"
DATABASE = "oroscope_aurora"
REGION = "ap-south-2"

COLUMN_NAMES = [
    "Ulcer", "Patch", "Growth", "Mucosal Condition", "Sharp Objects",
    "Pigmentation", "Symptoms", "Habits", "Oral Mapping",
    "Provisional Diagnosis", "Differential Diagnosis", "Advise",
]
DB_COLUMNS = [c.lower().replace(" ", "_") for c in COLUMN_NAMES]
KEY_FIELD_COUNT = 10

MAX_REQUEST_BYTES = 3 * 1024 * 1024  # 3 MiB safety margin under the real 4 MiB limit

def build_param_set(row):
    return [
        {"name": col, "value": {"stringValue": str(val)}}
        for col, val in zip(DB_COLUMNS, row)
    ]

def main():
    client = boto3.client("rds-data", region_name=REGION)

    wb = openpyxl.load_workbook(SOURCE_FILE, data_only=True, read_only=True)
    ws = wb["For new software"]
    rows = ws.iter_rows(values_only=True)
    header = next(rows)
    idx = {name: header.index(name) for name in COLUMN_NAMES}

    seen = {}
    for r in rows:
        key = tuple(r[idx[c]] for c in COLUMN_NAMES[:KEY_FIELD_COUNT])
        if key not in seen:
            seen[key] = [r[idx[c]] for c in COLUMN_NAMES]

    all_rows = list(seen.values())
    print(f"Loading {len(all_rows)} unique rows...")

    sql = f"""
        INSERT INTO clinical_rules ({', '.join(DB_COLUMNS)})
        VALUES ({', '.join(':' + c for c in DB_COLUMNS)})
    """

    inserted = 0
    batch = []
    batch_bytes = 0

    def flush(batch):
        nonlocal inserted
        if not batch:
            return
        for attempt in range(3):
            try:
                client.batch_execute_statement(
                    resourceArn=CLUSTER_ARN,
                    secretArn=SECRET_ARN,
                    database=DATABASE,
                    sql=sql,
                    parameterSets=batch,
                )
                break
            except client.exceptions.ClientError as e:
                if "DatabaseResumingException" in str(e) and attempt < 2:
                    print("  Database resuming, waiting 10s...")
                    time.sleep(10)
                    continue
                raise
        inserted += len(batch)
        print(f"  Inserted {inserted}/{len(all_rows)}")

    for row in all_rows:
        param_set = build_param_set(row)
        row_bytes = len(json.dumps(param_set))
        if batch_bytes + row_bytes > MAX_REQUEST_BYTES:
            flush(batch)
            batch, batch_bytes = [], 0
        batch.append(param_set)
        batch_bytes += row_bytes

    flush(batch)  # final partial batch
    print(f"Done. {inserted} rows loaded.")

if __name__ == "__main__":
    main()