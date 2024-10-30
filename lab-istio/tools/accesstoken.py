import jwt, json

def decode_access_token(token):
    try:
        # Decode the token without verification
        decoded_token = jwt.decode(token, options={"verify_signature": False})
        return decoded_token
    except jwt.ExpiredSignatureError:
        return "Token has expired"
    except jwt.InvalidTokenError:
        return "Invalid token"

# Example usage
if __name__ == "__main__":
    # Replace with your actual token
    token = "xyz"
    
    decoded_token = decode_access_token(token)
    print(json.dumps(decoded_token, indent=4))