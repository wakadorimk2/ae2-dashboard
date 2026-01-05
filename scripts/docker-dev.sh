#!/usr/bin/env bash
set -euo pipefail

IMAGE="ae2-dashboard:test"
CONTAINER_NAME="ae2-dashboard-dev"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

trap 'echo "Cleaning up container..."; docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true' EXIT INT TERM

echo "== AE2 Dashboard: docker local dev =="

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Error: .env not found at $ENV_FILE" >&2
  exit 1
fi

echo "Building image..."
docker build -t "$IMAGE" "$ROOT_DIR/collector"

echo "Running container..."
docker run --name "$CONTAINER_NAME" --rm -p 8080:8080 \
  --env-file "$ENV_FILE" \
  -v "$HOME/.config/gcloud:/root/.config/gcloud:ro" \
  "$IMAGE"
