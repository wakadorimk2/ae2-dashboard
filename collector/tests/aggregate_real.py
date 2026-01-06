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

while True:
    api_key = getpass.getpass("Enter API key: ")  # 非表示入力
    if api_key:
        break
    print("API key must not be empty. Please try again.")

headers = {
    "Content-Type": "application/json",
    "X-API-Key": api_key,
    "X-Timestamp": str(int(time.time())),
    "X-Nonce": str(uuid.uuid4()),
}

payload = {
    "network_id": NETWORK_ID
}

try:
    r = requests.post(
        f"{SERVICE_URL}/jobs/aggregate",
        headers=headers,
        json=payload,
        timeout=60,
    )
    print("status:", r.status_code)
    try:
        data = r.json()
        print(json.dumps(data, ensure_ascii=False, indent=2))
    except ValueError as e:
        print(f"Failed to parse response as JSON: {e}")
        try:
            print("Raw response text:")
            print(r.text)
        except UnicodeDecodeError as ue:
            print(f"Response could not be decoded as text: {ue}")
            print("Raw response content bytes:")
            print(repr(r.content))
except requests.exceptions.Timeout as e:
    print(f"Request timed out: {e}")
    raise SystemExit(1)
except requests.exceptions.ConnectionError as e:
    print(f"Network connection error during request: {e}")
    raise SystemExit(1)
except requests.exceptions.RequestException as e:
    print(f"HTTP request failed: {e}")
    raise SystemExit(1)