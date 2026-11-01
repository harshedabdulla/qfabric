# QFabric Quantum/PQC service image.
# Builds liboqs from a pinned release so liboqs-python finds a matching
# shared library and never tries to auto-download one at runtime.
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

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OQS_INSTALL_PATH=/opt/liboqs \
    LD_LIBRARY_PATH=/opt/liboqs/lib \
    QFABRIC_KEYSTORE_DIR=/data/keystore
COPY --from=liboqs /opt/liboqs /opt/liboqs
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
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
