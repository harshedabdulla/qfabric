"""Canonical audit manifest: the exact bytes signed for the ledger.

This is the integration contract with the Go chaincode
(blockchain/chaincode/qfabric-audit/transaction.go, ``CanonicalBytes``).
Spec: docs/API_CONTRACT.md section 4. Test vector:
integration/test_vectors/mldsa65_audit_manifest.json.

Format: header line, then ``key=value`` lines in FIELD_ORDER, joined with
"\\n", UTF-8, no trailing newline. Integers in base 10, no padding.
"""

from __future__ import annotations

HEADER = "QFABRIC-AUDIT-MANIFEST-V1"

FIELD_ORDER = (
    "sessionId",
    "sender",
    "receiver",
    "senderKeyId",
    "bb84Status",
    "qberPpm",
    "qberThresholdPpm",
    "siftedKeyLength",
    "finalKeyLength",
    "transcriptHash",
    "encryptionAlgorithm",
    "compression",
    "documentHash",
    "encryptedDocumentHash",
    "timestamp",
)


def to_ppm(rate: float) -> int:
    """Convert a rate in [0, 1] to integer parts-per-million (round half
    to even, as Python's ``round``). 0.02 -> 20000."""
    return round(rate * 1_000_000)


def canonical_manifest(manifest: dict) -> bytes:
    """Serialize a manifest dict (camelCase keys, exactly FIELD_ORDER) to
    canonical bytes. Reject missing/extra keys and any value containing
    "\\n" or "=" in identifiers (the Pydantic schema enforces formats)."""
    raise NotImplementedError("TODO(quantum-pqc): canonical_manifest")
