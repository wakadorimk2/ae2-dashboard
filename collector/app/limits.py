"""Centralized limit definitions for dashboard-related flows."""

# Cap how many items are considered when generating latest.json to bound cost.
INGEST_MAX = 500
# Hard ceiling for how many entries the /dashboard API may return.
API_MAX = 200
# Limit for ranking generation; keep aligned with API_MAX by default.
RANKING_MAX = API_MAX
