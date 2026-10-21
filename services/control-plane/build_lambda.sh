#!/usr/bin/env bash
# Builds fastapi_backend.zip for AWS Lambda (python3.13, x86_64).
# --platform/--only-binary make pip fetch Linux wheels even when run on another OS.
# boto3/botocore are removed: the Lambda runtime already provides them (saves ~30 MB).
set -euo pipefail
cd "$(dirname "$0")"

rm -rf package fastapi_backend.zip
pip install -r requirements.txt --target package \
  --platform manylinux2014_x86_64 --implementation cp --python-version 3.13 \
  --only-binary=:all: --upgrade --quiet
rm -rf package/boto3* package/botocore* package/s3transfer* package/jmespath*
cp -r app package/app
rm -rf package/app/tests   # tests and local-dev files must not ship in the Lambda
find package -name '__pycache__' -type d -prune -exec rm -rf {} +

python3 -c "import shutil; shutil.make_archive('fastapi_backend', 'zip', 'package')"
echo "Built fastapi_backend.zip: $(du -h fastapi_backend.zip | cut -f1) zipped, $(du -sm package | cut -f1) MB unzipped (limits: 50 MB / 250 MB)"