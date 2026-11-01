# Fabric network

Phase 2 uses the official **fabric-samples test network** rather than a hand-written network. It is downloaded here by `../scripts/start-network.sh`:

```
network/
├── install-fabric.sh        (downloaded, pinned to Fabric v2.5.16, git-ignored)
└── fabric-samples/          (git-ignored)
    ├── bin/                 peer, orderer, configtxgen, fabric-ca-client …
    ├── config/              core.yaml, orderer.yaml
    └── test-network/        network.sh, compose files, generated organizations/ and channel-artifacts/
```

Topology: 1 Raft orderer, `peer0.org1.example.com` (OrgA / Org1MSP), `peer0.org2.example.com` (OrgB / Org2MSP), one Fabric CA per org (`-ca`), and LevelDB state (set `FABRIC_STATE_DB=couchdb` for rich queries).

Generated crypto material (`test-network/organizations/`) contains private keys. It stays inside the git-ignored `fabric-samples/` directory and is destroyed by `stop-network.sh`.

If the demo outgrows the test network (custom org names, extra peers, separate hosts), move a custom `configtx.yaml`, `fabric-ca` configs and compose files into `network/config/`, `network/docker-compose/` and `network/scripts/`, and point the scripts there.
