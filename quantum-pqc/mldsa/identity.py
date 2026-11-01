"""Organization identities and the local key store.

The key store holds each organization's ML-DSA-65 secret key on the service
host. In the demo, both OrgA and OrgB live in one service. Layout under
``QFABRIC_KEYSTORE_DIR`` (git-ignored; a named volume in Docker):

    <dir>/                  mode 0700
      <orgId>.json          public identity (orgId, mspId, role, public key)
      <orgId>.key           raw secret key, mode 0600, created exclusively

Only public keys and fingerprints ever leave this module.
"""

from __future__ import annotations

import base64
import json
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from mldsa.keygen import generate_keypair, public_key_id
from mldsa.signing import sign

_ORG_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass(frozen=True)
class OrganizationIdentity:
    org_id: str
    display_name: str
    msp_id: str          # Fabric MSP the org maps to (e.g. Org1MSP)
    role: str            # MANUFACTURER | SUPPLIER
    public_key: bytes
    public_key_id: str
    created_at: str      # ISO-8601 UTC


class KeyStore:
    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self._lock = threading.Lock()

    def _paths(self, org_id: str) -> tuple[Path, Path]:
        if not _ORG_ID.match(org_id):  # also blocks path traversal
            raise ValueError(f"invalid orgId {org_id!r}")
        return self.directory / f"{org_id}.json", self.directory / f"{org_id}.key"

    def register(self, org_id: str, display_name: str, msp_id: str, role: str) -> OrganizationIdentity:
        """Generate and persist a key pair for a new organization.
        Raise ``FileExistsError`` if ``org_id`` is already registered."""
        meta_path, key_path = self._paths(org_id)
        with self._lock:
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            if meta_path.exists():
                raise FileExistsError(org_id)
            keypair = generate_keypair()
            identity = OrganizationIdentity(
                org_id=org_id, display_name=display_name, msp_id=msp_id, role=role,
                public_key=keypair.public_key, public_key_id=public_key_id(keypair.public_key),
                created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(keypair.secret_key)
            meta = {
                "orgId": org_id, "displayName": display_name, "mspId": msp_id, "role": role,
                "publicKey": base64.b64encode(keypair.public_key).decode(),
                "publicKeyId": identity.public_key_id, "createdAt": identity.created_at,
            }
            tmp = meta_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(meta, indent=2))
            tmp.replace(meta_path)  # metadata last: an org "exists" only once fully written
            return identity

    def get(self, org_id: str) -> OrganizationIdentity:
        """Return the public identity. Raise ``KeyError`` if unknown."""
        meta_path, _ = self._paths(org_id)
        try:
            meta = json.loads(meta_path.read_text())
        except FileNotFoundError:
            raise KeyError(org_id) from None
        return OrganizationIdentity(
            org_id=meta["orgId"], display_name=meta["displayName"], msp_id=meta["mspId"],
            role=meta["role"], public_key=base64.b64decode(meta["publicKey"]),
            public_key_id=meta["publicKeyId"], created_at=meta["createdAt"],
        )

    def sign_as(self, org_id: str, message: bytes) -> bytes:
        """Sign with the organization's secret key without exposing it."""
        _, key_path = self._paths(org_id)
        try:
            secret_key = key_path.read_bytes()
        except FileNotFoundError:
            raise KeyError(org_id) from None
        return sign(secret_key, message)
