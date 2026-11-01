"""BB84 quantum key distribution, simulated with Qiskit Aer.

BB84 is *quantum* cryptography (QKD), not post-quantum cryptography. Its
security rests on quantum measurement disturbance, not on a hard math
problem. Here it runs on a simulator; see docs/SECURITY_MODEL.md for the
assumptions that implies.

Public entry point: :func:`bb84.protocol.run_bb84`.

Basis encoding used across the package:
    0 = Z (rectilinear, |0>/|1>)
    1 = X (diagonal,    |+>/|->)
"""

from bb84.protocol import BB84Config, BB84Result, run_bb84

__all__ = ["BB84Config", "BB84Result", "run_bb84"]
