"""Organization identities and the local key store.

The key store holds each organization's ML-DSA-65 secret key on the
service host (demo setting: both OrgA and OrgB live in one service). Files
are written with mode 0600 under ``QFABRIC_KEYSTORE_DIR`` (git-ignored).
Only public keys and fingerprints ever leave this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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
        self.directory = directory

    def register(self, org_id: str, display_name: str, msp_id: str, role: str) -> OrganizationIdentity:
        """Generate and persist a key pair for a new organization.
        Raise ``FileExistsError`` if ``org_id`` is already registered."""
        raise NotImplementedError("TODO(quantum-pqc): KeyStore.register")

    def get(self, org_id: str) -> OrganizationIdentity:
        """Return the public identity. Raise ``KeyError`` if unknown."""
        raise NotImplementedError("TODO(quantum-pqc): KeyStore.get")

    def sign_as(self, org_id: str, message: bytes) -> bytes:
        """Sign with the organization's secret key without exposing it."""
        raise NotImplementedError("TODO(quantum-pqc): KeyStore.sign_as")
