import hashlib
import secrets


def generate_token() -> str:
    """A 256-bit URL-safe token. Only its hash is ever stored."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
