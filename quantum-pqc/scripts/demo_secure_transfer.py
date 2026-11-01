"""Demo: full secure transfer through the running API service.

Start the service first:  uvicorn api.main:app --port 8000
Then, from quantum-pqc/:  python -m scripts.demo_secure_transfer path/to/document [--eve]
"""

import argparse
import base64
import json
import os

import httpx2 as httpx

API = os.getenv("QFABRIC_CRYPTO_API_URL", "http://localhost:8000/api/v1")
ORGS = (("OrgA", "Manufacturer", "Org1MSP", "MANUFACTURER"), ("OrgB", "Supplier", "Org2MSP", "SUPPLIER"))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("document")
    p.add_argument("--eve", action="store_true", help="enable intercept-resend eavesdropper")
    a = p.parse_args()

    with httpx.Client(base_url=API, timeout=120) as c:
        for org_id, name, msp, role in ORGS:
            r = c.post("/organizations/register", json={"orgId": org_id, "displayName": name, "mspId": msp, "role": role})
            if r.status_code not in (201, 409):
                raise SystemExit(f"register {org_id}: {r.status_code} {r.text}")
        with open(a.document, "rb") as f:
            doc = base64.b64encode(f.read()).decode()
        r = c.post("/secure-transfer", json={"sender": "OrgA", "receiver": "OrgB", "document": doc,
                                             "simulateEavesdropper": a.eve, "channelErrorRate": 0.02})
        r.raise_for_status()
        body = r.json()
        body["signature"]["value"] = body["signature"]["value"][:24] + "..."
        print(json.dumps(body, indent=2))


if __name__ == "__main__":
    main()
