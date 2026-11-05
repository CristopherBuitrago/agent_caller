"""Adaptador de PiiHasher: HMAC-SHA256, compatible con hmac(texto, clave, 'sha256') de pgcrypto."""

import hashlib
import hmac


class HmacSha256PiiHasher:
    def __init__(self, key: str):
        if not key:
            raise ValueError("PII_HMAC_KEY vacía")
        self._key = key.encode()

    def hash(self, value: str) -> bytes:
        return hmac.new(self._key, value.encode(), hashlib.sha256).digest()
