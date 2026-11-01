"""ML-DSA-65 signing, verification, manifest canonicalization and
cross-language interop with the Go chaincode (cloudflare/circl)."""

import base64
import os
import stat

import pytest
from conftest import requires_liboqs

from mldsa import PUBLIC_KEY_SIZE, SIGNATURE_SIZE
from mldsa.identity import KeyStore
from mldsa.keygen import generate_keypair, public_key_id
from mldsa.manifest import canonical_manifest, to_ppm
from mldsa.signing import sign
from mldsa.verification import verify


def test_public_key_id_matches_vector(mldsa_vector):
    pk = base64.b64decode(mldsa_vector["publicKey"])
    assert public_key_id(pk) == mldsa_vector["publicKeyId"]


def test_to_ppm():
    assert to_ppm(0.02) == 20_000
    assert to_ppm(0.11) == 110_000


def test_canonical_manifest_matches_go_chaincode(mldsa_vector):
    assert canonical_manifest(mldsa_vector["manifest"]) == mldsa_vector["canonicalManifest"].encode()


def test_canonical_manifest_rejects_extra_fields(mldsa_vector):
    with pytest.raises(ValueError):
        canonical_manifest({**mldsa_vector["manifest"], "extra": "x"})


@requires_liboqs
def test_vector_signature_verifies_with_liboqs(mldsa_vector):
    """Interop gate: a CIRCL-produced signature must verify under liboqs."""
    pk = base64.b64decode(mldsa_vector["publicKey"])
    sig = base64.b64decode(mldsa_vector["signature"])
    assert verify(pk, mldsa_vector["canonicalManifest"].encode(), sig)


@requires_liboqs
def test_sign_verify_roundtrip_and_sizes():
    kp = generate_keypair()
    assert len(kp.public_key) == PUBLIC_KEY_SIZE
    sig = sign(kp.secret_key, b"qfabric")
    assert len(sig) == SIGNATURE_SIZE
    assert verify(kp.public_key, b"qfabric", sig)


@requires_liboqs
def test_tampered_message_and_wrong_key_fail():
    kp, other = generate_keypair(), generate_keypair()
    sig = sign(kp.secret_key, b"qber=0.02")
    assert not verify(kp.public_key, b"qber=0.01", sig)
    assert not verify(other.public_key, b"qber=0.02", sig)
    assert not verify(kp.public_key, b"qber=0.02", sig[:-1])


@requires_liboqs
def test_secret_key_not_in_repr():
    kp = generate_keypair()
    assert kp.secret_key.hex() not in repr(kp)


def test_canonical_manifest_rejects_line_injection(mldsa_vector):
    with pytest.raises(ValueError):
        canonical_manifest({**mldsa_vector["manifest"], "sessionId": "x\nsender=OrgC"})


def test_canonical_manifest_rejects_bool_as_int(mldsa_vector):
    with pytest.raises(ValueError):
        canonical_manifest({**mldsa_vector["manifest"], "finalKeyLength": True})


@requires_liboqs
def test_keystore_persists_keys_privately(tmp_path):
    store = KeyStore(tmp_path / "ks")
    identity = store.register("OrgA", "Manufacturer", "Org1MSP", "MANUFACTURER")
    key_file = tmp_path / "ks" / "OrgA.key"
    assert stat.S_IMODE(os.stat(key_file).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(tmp_path / "ks").st_mode) == 0o700
    assert store.get("OrgA") == identity
    assert verify(identity.public_key, b"m", store.sign_as("OrgA", b"m"))
    with pytest.raises(FileExistsError):
        store.register("OrgA", "Again", "Org1MSP", "MANUFACTURER")
    with pytest.raises(KeyError):
        store.get("OrgZ")
    with pytest.raises(ValueError):
        store.get("../etc")
