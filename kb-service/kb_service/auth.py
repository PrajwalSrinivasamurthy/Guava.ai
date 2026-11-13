"""Checking the API key that callers of the service present.

Only SHA-256 hashes of keys are stored on the server, so reading its configuration never
reveals a usable key. Several hashes can be active at once, which lets a key be rotated
without downtime: add the new hash, switch the caller over, then remove the old one.
"""

import hashlib
import hmac


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


class ApiKeyVerifier:
    def __init__(self, hashes: tuple[str, ...]):
        self._hashes = hashes

    def verify(self, key: str | None) -> bool:
        if not key:
            return False
        candidate = hash_key(key)
        matched = False
        for known in self._hashes:
            matched |= hmac.compare_digest(candidate, known)
        return matched
