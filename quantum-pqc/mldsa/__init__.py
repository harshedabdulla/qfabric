"""ML-DSA-65 (NIST FIPS 204) post-quantum signatures via liboqs.

Interop rule (must match the Go chaincode, which uses cloudflare/circl):
pure ML-DSA-65, empty context string, raw key/signature encodings from
FIPS 204. Sizes: public key 1952 B, secret key 4032 B, signature 3309 B.

Import ``oqs`` lazily inside functions so modules that do not sign can be
imported without liboqs installed.
"""

ALGORITHM = "ML-DSA-65"
PUBLIC_KEY_SIZE = 1952
SECRET_KEY_SIZE = 4032
SIGNATURE_SIZE = 3309
