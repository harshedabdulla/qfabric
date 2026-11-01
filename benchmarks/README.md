# Benchmarks

Plan, metrics and reporting template: [docs/BENCHMARKING.md](../docs/BENCHMARKING.md).

```
benchmarks/
├── cryptography/      Python (run with quantum-pqc/.venv): C1–C9
│   └── results/       raw CSV/JSON output (git-ignored)
└── blockchain/        Go, against the running test network: B1–B5
    └── results/       (git-ignored)
```

The subdirectories are created together with their first script (git does not track empty directories).

Conventions:

- One script per metric group, e.g. `cryptography/bench_signatures.py`, `cryptography/bench_bb84.py`, `blockchain/bench_record.go`.
- Each script writes `results/<metric>-<YYYYMMDD-HHMM>.csv` plus a JSON header with the environment (see BENCHMARKING.md §1).
- Use warm-up iterations and report p50/p95, not just the mean.
- Copy the final summary tables into `docs/BENCHMARKING.md` and the root README. Only measured numbers go there.
