from __future__ import annotations

import hashlib
import hmac


def build_hmac_signature(payload: bytes, secret_key: str) -> str:
    digest = hmac.new(secret_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"
