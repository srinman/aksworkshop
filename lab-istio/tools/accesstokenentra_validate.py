import jwt
import json
import requests
import os
from jwt.algorithms import RSAAlgorithm

def get_public_key(tenant_id, kid):
    # Fetch the OpenID Connect discovery document
    discovery_url = f"https://login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration"
    response = requests.get(discovery_url)
    jwks_uri = response.json()["jwks_uri"]

    # Fetch the public keys
    response = requests.get(jwks_uri)
    keys = response.json()["keys"]

    # Find the key with the matching kid
    for key in keys:
        if key["kid"] == kid:
            return RSAAlgorithm.from_jwk(json.dumps(key))
    raise Exception("Public key not found")

def decode_and_verify_access_token(token, tenant_id):
    try:
        # Decode the token header to get the kid
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header["kid"]

        # Get the public key
        public_key = get_public_key(tenant_id, kid)

        # Decode and verify the token without audience check
        decoded_token = jwt.decode(token, public_key, algorithms=["RS256"])
        return decoded_token
    except jwt.ExpiredSignatureError:
        return "Token has expired"
    except jwt.InvalidTokenError as e:
        return f"Invalid token: {e}"

# Example usage
if __name__ == "__main__":
    # Get token and tenant ID from environment variables
    token = os.getenv("JWT_TOKEN")
    tenant_id = os.getenv("TENANT_ID")

    if not token or not tenant_id:
        raise Exception("JWT_TOKEN and TENANT_ID environment variables must be set")
    
    decoded_token = decode_and_verify_access_token(token, tenant_id)
    print(json.dumps(decoded_token, indent=4))