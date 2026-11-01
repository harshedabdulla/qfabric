"""HKDF, compression and AES-256-GCM with tamper detection."""

import pytest

from encryption.compression import compress, decompress
from encryption.decryption import TamperDetectedError, decrypt_document
from encryption.encryption import encrypt_document
from encryption.key_derivation import associated_data, derive_aes_key

SECRET = bytes(range(32))
DOC = b"PURCHASE ORDER PO-2026-0042\n" * 50
MAX = 10 * 1024 * 1024


def test_derive_aes_key_is_32_bytes_and_context_bound():
    k1 = derive_aes_key(SECRET, "s1", "OrgA", "OrgB")
    assert len(k1) == 32
    assert k1 == derive_aes_key(SECRET, "s1", "OrgA", "OrgB")
    assert k1 != derive_aes_key(SECRET, "s2", "OrgA", "OrgB")
    assert k1 != derive_aes_key(SECRET, "s1", "OrgB", "OrgA")


@pytest.mark.parametrize("method", ["zstd", "gzip", "none"])
def test_compression_roundtrip(method):
    assert decompress(compress(DOC, method), method, MAX) == DOC


def test_decompression_bomb_is_refused():
    with pytest.raises(ValueError):
        decompress(compress(b"\0" * 2_000_000, "zstd"), "zstd", max_size=1_000_000)


def _encrypt():
    key = derive_aes_key(SECRET, "s1", "OrgA", "OrgB")
    aad = associated_data("s1", "OrgA", "OrgB")
    return key, aad, encrypt_document(key, DOC, aad, "zstd")


def test_encrypt_decrypt_roundtrip():
    key, aad, enc = _encrypt()
    assert len(enc.nonce) == 12
    assert enc.compressed_size < enc.original_size == len(DOC)
    assert decrypt_document(key, enc.nonce, enc.ciphertext, aad, "zstd", MAX) == DOC


def test_nonce_is_fresh_per_encryption():
    _, _, a = _encrypt()
    _, _, b = _encrypt()
    assert a.nonce != b.nonce


@pytest.mark.parametrize("field", ["ciphertext", "nonce", "aad"])
def test_tampering_is_detected(field):
    key, aad, enc = _encrypt()
    nonce, ct = enc.nonce, enc.ciphertext
    if field == "ciphertext":
        ct = ct[:-1] + bytes([ct[-1] ^ 1])
    elif field == "nonce":
        nonce = bytes([nonce[0] ^ 1]) + nonce[1:]
    else:
        aad = associated_data("s1", "OrgB", "OrgA")
    with pytest.raises(TamperDetectedError):
        decrypt_document(key, nonce, ct, aad, "zstd", MAX)
