import hashlib
import hmac
import secrets


def hash_api_key(api_key: str) -> str:
    """
    Computes a SHA-256 hexadecimal digest of an incoming API key.
    Plaintext keys are never stored in the database or cache.
    """
    return hashlib.sha256(api_key.strip().encode("utf-8")).hexdigest()


def generate_tenant_api_key() -> tuple[str, str]:
    """
    Generates a secure API key for tenant provisioning.
    Returns:
        tuple[str, str]: (plaintext_api_key, sha256_hash)
    """
    # 32 bytes of cryptographically strong entropy
    random_entropy = secrets.token_urlsafe(32)
    plaintext_key = f"sk_live_{random_entropy}"
    key_hash = hash_api_key(plaintext_key)
    return plaintext_key, key_hash


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    """
    Timing-attack resistant verification of an API key against a stored hash.
    """
    computed_hash = hash_api_key(raw_key)
    return hmac.compare_digest(computed_hash, stored_hash)