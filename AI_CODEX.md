# AI_CODEX.md

Operating instructions for **OpenAI Codex** in this repository.

> ⚠️ Read `AI_GUIDE.md` first. This file does not duplicate its content.

---

## 0. Overview

Codex's role in this project is limited to code completion and snippet generation,
within the constraints defined in `AI_GUIDE.md`.

---

## 1. Intended Use Cases

- Inline code completion for existing patterns
- Generating boilerplate that follows established conventions
- Translating pseudo-code or comments into concrete implementations

---

## 2. Constraints

- Observe all forbidden directories in `AI_GUIDE.md §3.1`
- Observe all dangerous operations in `AI_GUIDE.md §3.2`
- Do not add type definitions based on guesswork — follow `AI_GUIDE.md §4`
- Do not rewrite existing code for "improvement" without explicit instruction
- Do not include or suggest hardcoded secrets, tokens, or credentials

---

## 3. Out of Scope

The following are outside Codex's role in this project:

- Architectural decisions or design proposals
- Determining test strategy
- Executing or modifying deployment / infrastructure configuration
- Database migration authoring
- Security auditing

---

End of AI_CODEX.md
