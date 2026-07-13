from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CacheKeyPolicy:
    environment: str
    tenant_id: str
    schema_version: str = "v1"

    def build(self, namespace: str, opaque_identifier: str) -> str:
        if not namespace.replace("-", "").replace("_", "").isalnum():
            raise ValueError("cache namespace must be alphanumeric with dash/underscore")
        digest = hashlib.sha256(opaque_identifier.encode("utf-8")).hexdigest()
        return f"dcc:{self.environment}:{self.tenant_id}:{self.schema_version}:{namespace}:{digest}"
