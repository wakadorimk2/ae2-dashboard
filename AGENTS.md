# AGENTS.md

Operating instructions for **Codex** in this repository.
This file is automatically loaded by Codex.

> ⚠️ Read `AI_GUIDE.md` first. This file extends it — content is not duplicated here.

---

## 0. Overview

This file defines how Codex should:
- Choose its operating mode
- Explore the codebase efficiently
- Handle dangerous operations
- Format its output
- Respond to short human commands

---

## 1. Modes of Operation

### 1.1 Research Mode (Default — applies when mode is unspecified)

- ❌ No code changes
- ❌ No file edits
- ❌ No refactors
- ❌ No large directory exploration
- ✅ Read-only investigation
- ✅ Summaries, design proposals, risk identification

### 1.2 Implementation Mode

Only enter this mode when **explicitly instructed**.

Rules:
- Make **minimal, localized changes only**
- Prefer incremental diffs over large rewrites
- Respect the product philosophy in `AI_GUIDE.md §1`
- Avoid speculative abstractions or unrequested "improvements"
- **Completion condition**: `make test` must pass before declaring done

---

## 2. Exploration Protocol

Preferred order (most to least efficient):
1. **Grep** — search by content pattern
2. **Glob** — find files by path pattern
3. **Read** — read specific files

- Never enumerate directories before searching
- Restrict to code files: `.ts`, `.tsx`, `.js`, `.jsx`, `.html`, `.css`, `.py`
- Observe `AI_GUIDE.md §3.1` forbidden directories at all times

---

## 3. Dangerous Zone Reminders

See `AI_GUIDE.md §3.2` for the full list.

When a dangerous operation is encountered:
1. **Stop immediately**
2. State what was about to happen
3. Ask for explicit human confirmation before proceeding

Do not attempt workarounds or equivalent commands to achieve the same dangerous outcome.

---

## 4. Standard Output Format

Use this format for all responses in both modes.

### Research Mode Output

```
## Read Log
- <file path> — <why it was read>

## Assumptions
- <confirmed facts>
- ⚠️ <hypothesis or inference requiring human review>

## Current Structure Summary
- Strengths / Weaknesses / Key findings

## Gap Analysis / Design Proposal
- (if applicable)

## Risks
- Known risks in current design

## Verification
- Questions for human review
- Unresolved assumptions
```

### Implementation Mode Output

```
## Read Log
- <file path> — <why it was read>

## Assumptions
- <premises of this implementation>
- ⚠️ <uncertain premise requiring confirmation>

## Changes Summary
- List of changed files and what changed

## Impact
- What this change affects (components, APIs, tests)

## Risks
- Potential breakage, edge cases, side effects

## Rollback
- How to undo (git revert / migration down / etc.)

## Verification
- If code changed: `make test` is required (minimum)
- If docs-only: `Verification: N/A (docs-only)` is acceptable
- Manual checks if applicable
```

---

## 5. Short Commands

Humans may invoke modes with these phrases:

| Phrase | Action |
|---|---|
| `調査モード。AI_GUIDE.mdに従ってください。` | Enter Research Mode strictly |
| `実装モード。AI_GUIDE.mdを前提に最小差分で。` | Enter Implementation Mode |
| `調査モード` | Enter Research Mode |
| `実装モード` | Enter Implementation Mode |

Follow them strictly without requiring further clarification.

---

## 6. When in Doubt

- Do NOT guess silently
- List questions or missing assumptions explicitly under `## Assumptions`
- Ask before performing expensive exploration (more than 3 file reads for orientation)
- If a task seems to require a Dangerous Operation (`AI_GUIDE.md §3.2`), stop and ask

---

End of AGENTS.md
