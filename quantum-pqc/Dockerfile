# QFabric Quantum/PQC service image.
#  - liboqs is built from a pinned release so liboqs-python finds a matching
#    shared library and never tries to auto-download one at runtime.
#  - Qiskit is built from the vendored source in third_party/qiskit
#    (Qiskit 2.6.1), not from PyPI.
FROM python:3.12-slim AS liboqs
ARG LIBOQS_VERSION=0.16.0
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake ninja-build git libssl-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch ${LIBOQS_VERSION} https://github.com/open-quantum-safe/liboqs /src/liboqs \
    && cmake -S /src/liboqs -B /src/liboqs/build -GNinja \
        -DBUILD_SHARED_LIBS=ON -DOQS_BUILD_ONLY_LIB=ON -DCMAKE_INSTALL_PREFIX=/opt/liboqs \
    && cmake --build /src/liboqs/build \
    && cmake --install /src/liboqs/build

FROM python:3.12-slim AS qiskit
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
# Qiskit's release profile uses fat LTO with one codegen unit, which needs
# more RAM than a default 4 GB Docker VM has. Override it through Cargo's
# environment (no source changes): slightly slower binary, ~1/3 of the memory.
ENV PATH=/root/.cargo/bin:$PATH \
    CARGO_BUILD_JOBS=1 \
    CARGO_PROFILE_RELEASE_LTO=off \
    CARGO_PROFILE_RELEASE_CODEGEN_UNITS=16
COPY third_party/qiskit /src/qiskit
RUN pip wheel --no-deps --wheel-dir /wheels /src/qiskit

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OQS_INSTALL_PATH=/opt/liboqs \
    LD_LIBRARY_PATH=/opt/liboqs/lib \
    QFABRIC_KEYSTORE_DIR=/data/keystore \
    QFABRIC_QISKIT_SOURCE="quantum-pqc/third_party/qiskit (wheel built in image)"
COPY --from=liboqs /opt/liboqs /opt/liboqs
COPY --from=qiskit /wheels /wheels
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir /wheels/qiskit-*.whl && pip install --no-cache-dir -r requirements.txt && rm -rf /wheels
COPY bb84 ./bb84
COPY mldsa ./mldsa
COPY encryption ./encryption
COPY api ./api
RUN useradd --create-home --uid 10001 qfabric && mkdir -p /data/keystore && chown -R qfabric /data
USER qfabric
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')"
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
