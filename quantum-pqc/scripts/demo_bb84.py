"""Demo: BB84 with and without an intercept-resend eavesdropper.

Run from quantum-pqc/:  python -m scripts.demo_bb84 [--qubits 2048] [--noise 0.02]
"""

import argparse

from bb84 import BB84Config, run_bb84


def show(label: str, cfg: BB84Config) -> None:
    r = run_bb84(cfg)
    print(f"{label:<22} status={r.status:<8} qber={r.qber:.4f} sifted={r.sifted_key_length:<5} "
          f"final_bits={r.final_key_length:<4} reason={r.abort_reason.value if r.abort_reason else '-'}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--qubits", type=int, default=2048)
    p.add_argument("--noise", type=float, default=0.0)
    p.add_argument("--seed", type=int, default=42)
    a = p.parse_args()
    base = dict(num_qubits=a.qubits, channel_error_rate=a.noise, seed=a.seed)
    show("no eavesdropper", BB84Config(**base))
    show("Eve intercepts 30%", BB84Config(**base, eavesdropper=True, interception_rate=0.3))
    show("Eve intercepts 100%", BB84Config(**base, eavesdropper=True, interception_rate=1.0))


if __name__ == "__main__":
    main()
