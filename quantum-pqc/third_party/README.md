# Vendored third-party source

## Qiskit (`third_party/qiskit`)

QFabric's BB84 runs on Qiskit built **from this source tree**, not from a PyPI wheel. `pip install -e third_party/qiskit` compiles Qiskit's Rust core (`crates/`) and its Python package (`qiskit/`) from the files here, and the service imports Qiskit from this directory. `GET /api/v1/health` reports `"qiskitSource": "quantum-pqc/third_party/qiskit"` to prove it.

| | |
|---|---|
| Upstream | https://github.com/Qiskit/qiskit |
| Version | **2.6.1** (tag `2.6.1`, commit `2c4e5090d4eed225c8aab14e015864b0f8e26139`) |
| License | Apache-2.0 (`qiskit/LICENSE.txt`), the same license as QFabric |
| Local changes | None to source files |
| Removed to save space | `test/`, `releasenotes/`, `docs/`, `.github/`, `.binder/` (not needed to build or run) |

### What QFabric uses from it

| Qiskit API | Used in |
|---|---|
| `qiskit.QuantumCircuit`, `QuantumRegister`, `ClassicalRegister` | `bb84/alice.py`, `bb84/eavesdropper.py`, `bb84/bob.py` |
| Gates `x`, `h`, `measure`, `barrier`; circuit `copy`, `add_register` | same |
| (via qiskit-aer) `AerSimulator(method="stabilizer")`, `noise.pauli_error` | `bb84/quantum_channel.py` |

`qiskit-aer` (the simulator) is installed from PyPI and runs on top of this Qiskit build.

### Build

```bash
cd quantum-pqc
python3.12 -m venv .venv
.venv/bin/pip install -e third_party/qiskit     # needs Rust (https://rustup.rs); ~2 min
.venv/bin/python -c "import qiskit; print(qiskit.__version__, qiskit.__file__)"
```

`scripts/setup.sh crypto` does this automatically. Build outputs (`target/`, `*.so`, `qiskit.egg-info/`, generated `qiskit/capi` headers) are git-ignored.

### Updating

Replace the directory with a newer tag, prune the same directories, rebuild, run `pytest`, and update the version and commit above.
