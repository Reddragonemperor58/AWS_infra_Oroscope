"""Print a Cognito ID token for a doctor, for the API test scripts.

    read -s -p "Password: " COGNITO_PASSWORD; export COGNITO_PASSWORD; echo
    export ID_TOKEN=$(python scripts/get_token.py testdoctor@example.com)

The password comes from the COGNITO_PASSWORD environment variable, never from this file or the
command line, so it does not end up in git or in your shell history. Only the token is printed.
ID tokens expire after about an hour. Pool and client ids are not secret; override them with
COGNITO_USER_POOL_ID / COGNITO_CLIENT_ID / AWS_REGION if they ever change.
"""
import os
import sys

import boto3
from pycognito.aws_srp import AWSSRP

POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "ap-south-2_hNiSrJoWu")
CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID", "66qjof7hl6a1lnm87v9efij90v")
REGION = os.environ.get("AWS_REGION", "ap-south-2")

if len(sys.argv) != 2:
    sys.exit(__doc__)
password = os.environ.get("COGNITO_PASSWORD")
if not password:
    sys.exit("Set COGNITO_PASSWORD first (see usage above).")

client = boto3.client("cognito-idp", region_name=REGION)
srp = AWSSRP(username=sys.argv[1], password=password, pool_id=POOL_ID, client_id=CLIENT_ID, client=client)
try:
    tokens = srp.authenticate_user()
except client.exceptions.NotAuthorizedException:
    sys.exit("Incorrect username or password.")
print(tokens["AuthenticationResult"]["IdToken"])
