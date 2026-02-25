# GitHub Copilot Instructions

Instructions for **GitHub Copilot** (PR review and code completion) in this repository.

> Read `AI_GUIDE.md` for the shared constitution. This file adds Copilot-specific guidelines.

> **Note**: These instructions are primarily effective in Copilot Chat and PR Review. They may not be fully applied in Inline Completion.

---

## 0. Overview

Copilot's role in this project:
- **PR Review**: check for security issues, type safety, test coverage, and style consistency
- **Code Completion**: suggest code consistent with existing patterns

---

## 1. PR Review Focus Areas

### 1.1 Security

- Hardcoded secrets, API keys, tokens, or passwords in code or comments
- SQL injection risks (raw string queries without parameterization)
- XSS risks in frontend rendering
- Missing or bypassed API authentication (`X-API-Key`, `X-Nonce`, `X-Timestamp`)

### 1.2 Type Safety (TypeScript)

- Use of `any` without justification
- Missing return types on exported functions
- Mixing API response types with UI model types (see `AI_GUIDE.md §4`)

### 1.3 Product Philosophy Compliance

- Mobile-first violations (PC-only layout assumptions)
- Heavy UI elements (tables, DAGs, large lists) made permanently visible on the main screen — these should be activated by user action only (see `AI_GUIDE.md §1`)

### 1.4 Test Coverage

- New logic without corresponding tests
- Changes to `collector/` API handlers without `make test` evidence
- Edge cases not covered (e.g., empty responses, unknown `kind` values)

### 1.5 Dangerous Zone Compliance

- Flag any PR that touches `migrations/`, deploy scripts, or `.env` references
- See `AI_GUIDE.md §3.2` for the full dangerous operations list

---

## 2. Code Completion Guidelines

- Follow existing naming conventions (snake_case for Python, camelCase/PascalCase for TypeScript per context)
- Use minimal types consistent with `AI_GUIDE.md §4` — do not suggest heavy type hierarchies
- Do not introduce new dependencies without noting them explicitly

---

## 3. Do NOT Suggest

- Changes to `migrations/` files
- Hardcoding environment variables or secrets
- Large-scale refactors unrelated to the PR scope
- Switching UI frameworks or major libraries
- Removing existing API endpoints or changing their signatures without explicit context

---

End of copilot-instructions.md
