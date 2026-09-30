import json

from cryptography.fernet import InvalidToken

from app.core.security import decrypt_data, encrypt_data


def encrypt_json(data: dict) -> str:
    return encrypt_data(json.dumps(data))


def decrypt_json(token: str | None) -> dict:
    if not token:
        return {}
    try:
        return json.loads(decrypt_data(token))
    except InvalidToken as exc:
        raise RuntimeError(
            "Could not decrypt integration secrets. FERNET_SECRET_KEY has changed since they were saved."
        ) from exc