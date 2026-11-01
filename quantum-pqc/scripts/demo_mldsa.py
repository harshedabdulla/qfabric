"""Demo: ML-DSA-65 key generation, signing, verification, tamper detection.

Run from quantum-pqc/:  python -m scripts.demo_mldsa
"""

import time

from mldsa.keygen import generate_keypair, public_key_id
from mldsa.signing import sign
from mldsa.verification import verify


def main() -> None:
    t = time.perf_counter()
    kp = generate_keypair()
    print(f"keygen      {1000 * (time.perf_counter() - t):7.2f} ms  pk={len(kp.public_key)} B  id={public_key_id(kp.public_key)[:16]}...")
    msg = b"QFABRIC-AUDIT-MANIFEST-V1\nsessionId=demo"
    t = time.perf_counter()
    sig = sign(kp.secret_key, msg)
    print(f"sign        {1000 * (time.perf_counter() - t):7.2f} ms  sig={len(sig)} B")
    t = time.perf_counter()
    ok = verify(kp.public_key, msg, sig)
    print(f"verify      {1000 * (time.perf_counter() - t):7.2f} ms  valid={ok}")
    print(f"tampered    valid={verify(kp.public_key, msg + b'!', sig)}  (expected False)")


if __name__ == "__main__":
    main()
