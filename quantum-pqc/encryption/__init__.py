"""Document protection with BB84-derived keys.

Pipeline: plaintext -> compress -> AES-256-GCM(key = HKDF(BB84 secret)).
Compression happens before encryption because ciphertext does not compress.
"""

ALGORITHM = "AES-256-GCM"
NONCE_SIZE = 12   # bytes, random per message
TAG_SIZE = 16     # bytes, appended to ciphertext (cryptography's AESGCM layout)
