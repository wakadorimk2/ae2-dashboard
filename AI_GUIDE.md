# AI_GUIDE.md
This file defines how AI tools (e.g. OpenAI Codex) should interact with this repository.
The goal is to reduce wasted exploration and keep changes aligned with the product philosophy.

---

## 0. Purpose / Context

This repository contains:
- A dashboard UI for visualizing AE2-related data
- Backend collectors and Cloud Run deployment
- Very large static asset directories (icons, etc.)

⚠️ Naive full-repository scanning is expensive and counterproductive.
AI tools must follow the rules below.

---

## 1. Product & UI Philosophy (Very Important)

- **Mobile-first**
  - The smartphone view is the baseline.
  - PC views only add *supplementary* information or layout, not new meaning.

- **Heatmap-first**
  - The heatmap is the primary UI.
  - It represents the “world state” at a glance.

- **Separation of concerns**
  - Heatmap: overview / observation
  - List (table): explicit inspection → separate page or view
  - DAG: reasoning / causality → activated by tapping a heatmap cell

- **Interaction model**
  - Users *observe first*, then *dig deeper by action*.
  - Nothing heavy (tables, DAGs) should be always visible on the main screen.

---

## 2. Exploration Rules (Strict)

### 2.1 Forbidden directories
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

---

### 2.2 How to explore correctly
- Prefer **ripgrep-style searches** over directory traversal
- Focus on:
  - UI entry points
  - Routing
  - API fetch logic
  - JSON keys actually referenced by the UI
- Restrict attention to code files (`.ts`, `.tsx`, `.js`, `.jsx`, `.html`, `.css`, `.py`)

---

## 3. Modes of Operation

### 3.1 Research Mode (Default when unspecified)

- ❌ No code changes
- ❌ No file edits
- ❌ No refactors
- ✅ Read-only investigation
- ✅ Summaries, design proposals, and risk identification

Expected output:
- Key files and their responsibilities
- Current data flow (textual diagram is fine)
- Minimal vs recommended change strategies
- Unknowns and assumptions

---

### 3.2 Implementation Mode

Only enter this mode if explicitly stated.

Rules:
- Make **minimal, localized changes**
- Prefer incremental diffs over large rewrites
- Respect the UI philosophy described above
- Avoid speculative abstractions

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

## 5. When in Doubt

- Do NOT guess silently
- List questions or missing assumptions explicitly
- Ask before performing expensive exploration

---

## 6. Short Commands for Humans

Humans may invoke modes using short phrases:

- “調査モード。AI_GUIDE.mdに従ってください。”
- “実装モード。AI_GUIDE.mdを前提に最小差分で。”

Follow them strictly.

---

End of AI_GUIDE.md
