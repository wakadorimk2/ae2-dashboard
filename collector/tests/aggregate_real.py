import os
import time
import uuid
import json
import getpass
import requests

# ---- config from env ----
SERVICE_URL = os.getenv("SERVICE_URL")
if not SERVICE_URL:
    raise RuntimeError("SERVICE_URL is not set")

NETWORK_ID = os.getenv("NETWORK_ID", "base-main")
# -------------------------

api_key = getpass.getpass("")  # 非表示入力

headers = {
    "content-type": "application/json",
    "X-API-Key": api_key,
    "X-Timestamp": str(int(time.time())),
    "X-Nonce": str(uuid.uuid4()),
}

payload = {
    "network_id": NETWORK_ID
}

r = requests.post(
    f"{SERVICE_URL}/jobs/aggregate",
    headers=headers,
    json=payload,
    timeout=60,
)

print("status:", r.status_code)
try:
    print(json.dumps(r.json(), ensure_ascii=False, indent=2))
except Exception:
    print(r.text)
