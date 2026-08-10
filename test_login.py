from pycognito.aws_srp import AWSSRP
import boto3

# Paste your Terraform outputs here
POOL_ID = "ap-south-2_hNiSrJoWu"
CLIENT_ID = "66qjof7hl6a1lnm87v9efij90v"

# The client handles the API calls, the AWSSRP class handles the math
cognito_client = boto3.client('cognito-idp', region_name='ap-south-2')

aws_srp = AWSSRP(
    username="testdoctor@example.com",
    password="Oroscope!2026Secure",
    pool_id=POOL_ID,
    client_id=CLIENT_ID,
    client=cognito_client
)

# Negotiate the cryptographic tokens
tokens = aws_srp.authenticate_user()

print("✅ SRP Authentication Successful!")
print(f"ID Token (JWT): {tokens['AuthenticationResult']['IdToken'][:50]}...")