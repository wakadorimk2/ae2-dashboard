"""Manual integration test script for Aggregate endpoint (not run by pytest)."""

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
    api_key = getpass.getpass("Enter API key: ")  # Prompt for API key (hidden input, 非表示入力)
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
    response = requests.post(
        f"{SERVICE_URL}/jobs/aggregate",
        headers=headers,
        json=payload,
        timeout=60,
    )
    print("status:", response.status_code)

    if response.ok:
        print("Request succeeded.")
    else:
        print("Request failed (non-2xx response).")

    # まずは JSON をできる限り表示
    try:
        data = response.json()
        print(json.dumps(data, ensure_ascii=False, indent=2))
    except requests.exceptions.JSONDecodeError as decode_err:
        print(f"Failed to parse response as JSON: {decode_err}")
        print("Raw response text:")
        print(response.text)
        print("Raw response content bytes:")
        print(repr(response.content))
        raise SystemExit(1) from decode_err

    # 最後に一回だけ成功/失敗を判定して終了
    if response.ok:
        print("Request succeeded.")
    else:
        print(f"Request failed (status={response.status_code}).")
        raise SystemExit(1)

except requests.exceptions.RequestException as req_err:
    if isinstance(req_err, requests.exceptions.Timeout):
        print(f"Request timed out: {req_err}")
    elif isinstance(req_err, requests.exceptions.ConnectionError):
        print(f"Network connection error during request: {req_err}")
    else:
        print(f"HTTP request failed: {req_err}")
    raise SystemExit(1) from req_err