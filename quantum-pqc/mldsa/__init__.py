"""ML-DSA-65 (NIST FIPS 204) post-quantum signatures via liboqs.

Interop rule (must match the Go chaincode, which uses cloudflare/circl):
pure ML-DSA-65, empty context string, raw key/signature encodings from
FIPS 204. Sizes: public key 1952 B, secret key 4032 B, signature 3309 B.

Import ``oqs`` lazily inside functions so modules that do not sign can be
imported without liboqs installed.
"""

import os
from pathlib import Path

_LOCAL_LIBOQS = Path(__file__).resolve().parent.parent / ".oqs"
if "OQS_INSTALL_PATH" not in os.environ and (_LOCAL_LIBOQS / "lib").is_dir():
    # scripts/setup.sh builds liboqs into quantum-pqc/.oqs (git-ignored).
    os.environ["OQS_INSTALL_PATH"] = str(_LOCAL_LIBOQS)

ALGORITHM = "ML-DSA-65"
PUBLIC_KEY_SIZE = 1952
SECRET_KEY_SIZE = 4032
SIGNATURE_SIZE = 3309
