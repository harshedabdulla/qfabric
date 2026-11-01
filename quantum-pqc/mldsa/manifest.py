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

INTEGER_FIELDS = frozenset({"qberPpm", "qberThresholdPpm", "siftedKeyLength", "finalKeyLength"})


def to_ppm(rate: float) -> int:
    """Convert a rate in [0, 1] to integer parts-per-million (round half
    to even, as Python's ``round``). 0.02 -> 20000."""
    return round(rate * 1_000_000)


def canonical_manifest(manifest: dict) -> bytes:
    """Serialize a manifest dict (camelCase keys, exactly FIELD_ORDER) to
    canonical bytes. Rejects missing or extra keys, wrong value types, and
    values containing line breaks."""
    keys = set(manifest)
    if keys != set(FIELD_ORDER):
        missing, extra = set(FIELD_ORDER) - keys, keys - set(FIELD_ORDER)
        raise ValueError(f"manifest fields mismatch (missing={sorted(missing)}, extra={sorted(extra)})")
    lines = [HEADER]
    for name in FIELD_ORDER:
        value = manifest[name]
        if hasattr(value, "value"):  # str Enum from the Pydantic model
            value = value.value
        if name in INTEGER_FIELDS:
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
            text = str(value)
        else:
            if not isinstance(value, str):
                raise ValueError(f"{name} must be a string")
            text = value
        if "\n" in text or "\r" in text:
            raise ValueError(f"{name} must not contain line breaks")
        lines.append(f"{name}={text}")
    return "\n".join(lines).encode("utf-8")
