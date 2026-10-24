"""Print a Cognito ID token for a doctor, for the API test scripts.

    read -s -p "Password: " COGNITO_PASSWORD; export COGNITO_PASSWORD; echo
    export ID_TOKEN=$(python scripts/get_token.py testdoctor@example.com)

If the account has two-step sign-in (authenticator app), also give the current 6-digit code:

    read -p "Code from your authenticator app: " COGNITO_MFA_CODE; export COGNITO_MFA_CODE
    export ID_TOKEN=$(python scripts/get_token.py testdoctor@example.com)

Codes change every 30 seconds, so type a fresh one each time. A brand-new account must enrol its
authenticator app once by logging in to the web app (the script cannot show the QR code).

The password comes from the COGNITO_PASSWORD environment variable, never from this file or the
command line, so it does not end up in git or in your shell history. Only the token is printed.
ID tokens expire after about an hour. Pool and client ids are not secret; override them with
COGNITO_USER_POOL_ID / COGNITO_CLIENT_ID / AWS_REGION if they ever change.
"""
import os
import sys

import boto3
from pycognito.aws_srp import AWSSRP
from pycognito.exceptions import SoftwareTokenMFAChallengeException

POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "ap-south-2_hNiSrJoWu")
CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID", "66qjof7hl6a1lnm87v9efij90v")
REGION = os.environ.get("AWS_REGION", "ap-south-2")


def get_id_token(username, password, mfa_code, client):
    srp = AWSSRP(username=username, password=password, pool_id=POOL_ID, client_id=CLIENT_ID, client=client)
    try:
        tokens = srp.authenticate_user()
    except SoftwareTokenMFAChallengeException as exc:
        if not mfa_code:
            sys.exit("This account uses two-step sign-in. Set COGNITO_MFA_CODE to the current 6-digit code (see usage above).")
        challenge = exc.get_tokens()
        tokens = client.respond_to_auth_challenge(
            ClientId=CLIENT_ID,
            ChallengeName="SOFTWARE_TOKEN_MFA",
            Session=challenge["Session"],
            ChallengeResponses={"USERNAME": username, "SOFTWARE_TOKEN_MFA_CODE": mfa_code},
        )
    if "AuthenticationResult" not in tokens:
        if tokens.get("ChallengeName") == "MFA_SETUP":
            sys.exit("This account has not set up its authenticator app yet. Log in once in the web app to do that, then try again.")
        sys.exit("Sign-in needs another step this script cannot do: " + str(tokens.get("ChallengeName")))
    return tokens["AuthenticationResult"]["IdToken"]


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    password = os.environ.get("COGNITO_PASSWORD")
    if not password:
        sys.exit("Set COGNITO_PASSWORD first (see usage above).")
    client = boto3.client("cognito-idp", region_name=REGION)
    try:
        token = get_id_token(sys.argv[1], password, os.environ.get("COGNITO_MFA_CODE"), client)
    except (client.exceptions.NotAuthorizedException, client.exceptions.CodeMismatchException) as exc:
        sys.exit("Sign-in failed: " + ("wrong username, password or code." if "NotAuthorized" in type(exc).__name__ or "CodeMismatch" in type(exc).__name__ else str(exc)))
    print(token)


if __name__ == "__main__":
    main()
