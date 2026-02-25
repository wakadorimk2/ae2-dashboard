# AI_GUIDE.md

This file is the **shared constitution** for all AI tools working with this repository.
Each AI tool has its own operating instructions file — read this first, then your tool-specific file.

> Tool-specific instructions:
> - Claude Code → `CLAUDE.md`
> - GitHub Copilot → `.github/copilot-instructions.md`
> - OpenAI Codex → `AI_CODEX.md`

---

## 0. Purpose & Scope

This repository contains:
- A dashboard UI for visualizing AE2 (Applied Energistics 2) inventory data from Minecraft
- Backend collectors and Cloud Run deployment
- Very large static asset directories (icons, etc.)

⚠️ Naive full-repository scanning is expensive and counterproductive.
All AI tools must follow the rules in this file and their respective tool-specific files.

---

## 1. Product & UI Philosophy

- **Mobile-first**
  - The smartphone view is the baseline.
  - PC views only add *supplementary* information or layout, not new meaning.

- **Primary display: Heatmap**
  - The heatmap is one of the primary display components in the current implementation.
  - It is not a fixed design principle — the UI may evolve.

- **Separation of concerns**
  - Heatmap: overview / observation
  - List (table): explicit inspection → separate page or view
  - DAG: reasoning / causality → activated by tapping a heatmap cell

- **Interaction model**
  - Users *observe first*, then *dig deeper by action*.
  - Nothing heavy (tables, DAGs) should be always visible on the main screen.

---

## 2. Architecture Overview

> Source: `README.md`. Items not found in that source are marked TBD.

### Tech Stack

| Layer | Technology |
|---|---|
| Game client | CC:Tweaked (Lua) in Minecraft |
| Backend | FastAPI (Python 3.12+) |
| Frontend | Vite + TypeScript (SPA) |
| Database | PostgreSQL |
| Object storage | GCS (Google Cloud Storage) |
| Hosting | Cloud Run |

### Key Directories

```
ae2-dashboard/
├── cc/                          Lua scripts (CC:Tweaked in Minecraft)
├── collector/                   FastAPI backend
│   └── app/ops_ui/ui-src/       Vite frontend source
├── migrations/                  PostgreSQL schema SQL
└── scripts/                     Shell scripts (env, Docker, deploy)
```

### Data Flow

```
CC:Tweaked (Lua) ──POST /ingest──► FastAPI ──► GCS (snapshots)
                                           └──► PostgreSQL (inventory_*)

Browser ──GET /dashboard/ui──► Vite SPA
```

---

## 3. Forbidden Zones

### 3.1 Forbidden Directories

The following directories are **large or irrelevant** to logic analysis.
Do NOT scan, enumerate, or open files inside them.

- `**/static/icons/**`
- `collector/app/ops_ui/static/icons/**`
- `**/node_modules/**`
- `**/dist/**`
- `**/build/**`
- `**/.venv/**`
- `**/__pycache__/**`
- `**/.git/**`

If information seems to be missing, ask instead of exploring these paths.

### 3.2 Dangerous Operations

AI tools must NOT perform the following operations independently.
Stop and request explicit human confirmation before proceeding.

**Category A — Strictly Forbidden (requires explicit human approval)**

- Any changes to `migrations/` (irreversible DB schema changes)
- Running `make deploy` or any deploy-related script in `scripts/`
- Modifying Cloud Run / GCP infrastructure configuration
- Reading, writing, or referencing `.env` / secrets / credential files
- `git push --force` or `git reset --hard` on any shared branch
- Direct commits to `main`

**Category B — Stop and confirm before proceeding**

- Deleting or overwriting files in GCS buckets
- Direct SQL with `DROP` / `TRUNCATE` / bulk `DELETE`
- Major version upgrades of packages
- Deleting or renaming public API endpoints
- Modifying `collector/requirements*.txt`

---

## 4. Data & Type Safety Direction

- TypeScript is preferred for frontend-facing data structures
- Start with **minimal types**, extend later
- Separate concerns clearly:
  - Raw numeric values vs display-friendly values
  - API response shape vs UI-specific models

Example (conceptual):
- `DashboardResponse`
- `HeatmapCell`
- `ItemRow`
- `kind: 'item' | 'fluid' | 'gas'`

---

## 5. Security Rules

- Never include secrets, API keys, tokens, or passwords in any output, commit, or suggestion
- Never read or reference `.env` files or credential files
- Do not log or print sensitive values, even in debug contexts
- If a secret appears to be hardcoded in existing code, flag it as a risk — do not copy or propagate it

---

## 6. Commit & PR Conventions

- Commit messages: follow Conventional Commits format
  - Prefixes: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`
- Branch naming: `feat/<description>`, `fix/<description>`, `chore/<description>`
- Direct commits to `main` are **prohibited** — all changes go through PRs
- PRs must pass Copilot review and `make test` before merge (see `.github/pull_request_template.md`)

---

## 7. Changelog

| Date | Change |
|---|---|
| 2026-02-25 | v2: Restructured as shared constitution. Moved tool-specific content to CLAUDE.md. Added Architecture Overview, Dangerous Operations, Security Rules, Commit/PR Conventions. Downgraded Heatmap from design principle to implementation note. |

---

End of AI_GUIDE.md
