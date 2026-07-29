import hashlib
import secrets
import bcrypt


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def generate_session_id() -> str:
    return secrets.token_urlsafe(32)


def generate_token(user_id: int, username: str, secret: str, expiry_hours: int = 24) -> str:
    import hmac
    import json
    import time

    payload = {
        "user_id": user_id,
        "username": username,
        "exp": int(time.time()) + expiry_hours * 3600,
    }
    payload_b64 = __import__("base64").urlsafe_b64encode(
        json.dumps(payload).encode()
    ).decode()

    sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()

    return f"{payload_b64}.{sig}"


def verify_token(token: str, secret: str) -> dict | None:
    import hmac
    import json
    import time
    import base64

    try:
        payload_b64, sig = token.split(".", 1)
    except ValueError:
        return None

    expected_sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        return None

    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    if payload.get("exp", 0) < time.time():
        return None

    return payload
