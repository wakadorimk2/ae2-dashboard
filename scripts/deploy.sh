#!/usr/bin/env bash
set -euo pipefail

ENV_FILE=".env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  echo "Loaded .env from $ENV_FILE"
else
  echo "Warning: .env not found, continuing without it" >&2
fi

: "${GCP_PROJECT:?Error: GCP_PROJECT is not set}"
: "${SERVICE:?Error: SERVICE is not set}"
REGION="${REGION:-us-west1}"

# App env (adjust keys to match your code)
: "${GCS_BUCKET:?Error: GCS_BUCKET is not set}"
: "${GOOGLE_CLOUD_PROJECT:?Error: GOOGLE_CLOUD_PROJECT is not set}"

if ! command -v gcloud >/dev/null 2>&1; then
  echo "Error: gcloud not found. Install the Google Cloud SDK." >&2
  exit 1
fi

gcloud config set project "$GCP_PROJECT"

ALLOW_FLAG=()
if [[ "${ALLOW_UNAUTHENTICATED:-}" == "true" ]]; then
  ALLOW_FLAG+=(--allow-unauthenticated)
fi

SOURCE_DIR="${SOURCE_DIR:-collector}"
if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "Error: source directory '$SOURCE_DIR' not found." >&2
  exit 1
fi

echo "Deploying to Cloud Run: service=$SERVICE region=$REGION project=$GCP_PROJECT source=$SOURCE_DIR"

pushd "$SOURCE_DIR" >/dev/null
gcloud run deploy "$SERVICE" --quiet \
  --source . \
  --region "$REGION" \
  --set-env-vars "GCS_BUCKET=$GCS_BUCKET,GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT" \
  "${ALLOW_FLAG[@]}"
popd >/dev/null

SERVICE_URL="$(gcloud run services describe "$SERVICE" \
  --region "$REGION" \
  --format='value(status.url)' 2>/dev/null || true)"

if [[ -n "$SERVICE_URL" ]]; then
  echo "Service URL: $SERVICE_URL"
else
  echo "Service URL: (not available)"
fi
