"""Information reconciliation: make Bob's key equal to Alice's.

This is the Cascade protocol (Brassard and Salvail, 1993):

* Pass 1 uses block size ``k1 = ceil(0.73 / QBER)``. Each later pass doubles
  the block size (capped at n/2) and works on a fresh public random
  permutation.
* For each block, Alice discloses its parity. If Bob's parity differs, they
  binary-search the block (Alice discloses each half-parity) and Bob flips
  the located bit.
* **Cascade step (backtracking):** flipping a bit changes the parity of the
  blocks containing it in every other pass. Any block that now mismatches
  Alice's already-disclosed parity is searched again. This is how error
  pairs hidden in even-parity blocks get found.

Every parity Alice discloses counts as one leaked bit. Privacy amplification
subtracts that leakage. Residual errors are caught by key confirmation in
:mod:`bb84.protocol`.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

import numpy as np


@dataclass
class ErrorCorrectionResult:
    corrected_key: np.ndarray        # Bob's key after correction
    bits_leaked: int                 # parity bits revealed on the public channel
    passes: int
    errors_corrected: int
    method: str = "cascade"
    messages: list[dict] = field(default_factory=list)  # public messages, for the transcript


def initial_block_size(n: int, qber: float) -> int:
    return max(4, min(max(n // 2, 1), math.ceil(0.73 / max(qber, 0.01))))


def _parity(bits: np.ndarray) -> int:
    return int(np.bitwise_xor.reduce(bits)) if bits.size else 0


@dataclass
class _Pass:
    order: np.ndarray        # permutation of key positions
    block: int               # block size
    block_of: np.ndarray     # key position -> block index in this pass
    alice_parity: list[int]  # Alice's disclosed parity per block

    def members(self, b: int) -> np.ndarray:
        return self.order[b * self.block:(b + 1) * self.block]


def reconcile(
    alice_key: np.ndarray,
    bob_key: np.ndarray,
    qber: float,
    rng: np.random.Generator,
    passes: int = 4,
    start_pass: int = 0,
) -> ErrorCorrectionResult:
    """Run ``passes`` Cascade passes (with backtracking) on a copy of Bob's key.

    ``rng`` drives the public permutations (its output is public).
    ``start_pass`` continues with larger blocks when a previous round failed
    key confirmation.
    """
    if alice_key.shape != bob_key.shape:
        raise ValueError("keys must have the same length")
    n = alice_key.size
    bob = bob_key.copy()
    leaked = corrected = 0
    history: list[_Pass] = []
    messages: list[dict] = []
    cap = max(4, n // 2)
    block = min(cap, initial_block_size(n, qber) * (2**start_pass))

    def binary_search(members: np.ndarray, disclosed: list[int]) -> int:
        nonlocal leaked
        lo, hi = 0, members.size
        while hi - lo > 1:
            mid = (lo + hi) // 2
            half = _parity(alice_key[members[lo:mid]])
            disclosed.append(half)
            leaked += 1
            if half != _parity(bob[members[lo:mid]]):
                hi = mid
            else:
                lo = mid
        return int(members[lo])

    for p in range(start_pass, start_pass + passes):
        perm_seed = int(rng.integers(0, 2**63))
        order = np.arange(n) if p == 0 else np.random.default_rng(perm_seed).permutation(n)
        block_of = np.empty(n, dtype=np.int64)
        block_of[order] = np.arange(n) // block
        current = _Pass(order, block, block_of, [])
        history.append(current)
        disclosed: list[int] = []

        queue: deque[tuple[_Pass, int]] = deque()
        for b in range(math.ceil(n / block)):
            parity = _parity(alice_key[current.members(b)])
            current.alice_parity.append(parity)
            disclosed.append(parity)
            leaked += 1
            if parity != _parity(bob[current.members(b)]):
                queue.append((current, b))

        while queue:
            ps, b = queue.popleft()
            members = ps.members(b)
            if ps.alice_parity[b] == _parity(bob[members]):
                continue  # already fixed by an earlier cascade step
            position = binary_search(members, disclosed)
            bob[position] ^= 1
            corrected += 1
            for other in history:
                if other is ps:
                    continue
                ob = int(other.block_of[position])
                if other.alice_parity[ob] != _parity(bob[other.members(ob)]):
                    queue.append((other, ob))

        messages.append({
            "pass": p,
            "blockSize": int(block),
            "permutationSeed": perm_seed if p else None,
            "aliceParities": np.packbits(np.array(disclosed, dtype=np.uint8)).tobytes().hex(),
            "parityCount": len(disclosed),
        })
        block = min(cap, block * 2)

    return ErrorCorrectionResult(corrected_key=bob, bits_leaked=leaked, passes=passes,
                                 errors_corrected=corrected, messages=messages)
