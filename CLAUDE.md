# AGENTS GUIDELINES

## Tabla de contenidos

- [0. Language & Token Efficiency](#0-language--token-efficiency)
- [1. Think Before Coding](#1-think-before-coding)
- [2. Goal-Driven Execution](#2-goal-driven-execution)
- [3. Simplicity First](#3-simplicity-first)
- [4. Surgical Changes](#4-surgical-changes)
- [5. Version Control](#5-version-control)

<!-- <language_efficiency> -->

## 0. Language & Token Efficiency

**Optimize for clarity externally, efficiency internally.**

- Internal reasoning may be conducted in English to optimize token usage and reduce verbosity.
- All user-facing responses MUST be in Spanish.
- Comments generated or modified in source code MUST also be in Spanish.
- Messages generated for `git commit` MUST also be in Spanish.
- Exception: keep highly standardized technical terms in English when:
  - translating them adds no value, or
  - translation introduces ambiguity (e.g., "prompt", "token", "runtime", "framework", "API").
- This exception applies equally to user responses and code comments.
- Do not mix languages unnecessarily. Default to Spanish unless there is a clear technical reason not to.
<!-- </language_efficiency> -->

---

<!-- <think_before_coding> -->

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:

- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach achieves the same result with less code or fewer moving parts, propose it before implementing the requested one. If the request conflicts with an existing requirement, constraint, or invariant, name the conflict and stop instead of resolving it silently.
- If something is unclear, stop. Name what's confusing. Ask.
<!-- </think_before_coding> -->

---

<!-- <goal_driven_execution> -->

## 2. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals. When a test framework is configured, prefer a test-first approach:

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

When no test framework is configured yet, define the success criterion as an executable check (a command, script, or observable output) or, failing that, a bounded manual review against the stated requirement.

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

<!-- </goal_driven_execution> -->

---

<!-- <simplicity_first> -->

## 3. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- No speculative or preventive infrastructure (abstractions, tooling, "while we're here" additions) unless the user explicitly scoped it.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### No unapproved artifacts or automation

The same principle extends beyond code to files, tooling, and process: do not add what the user did not explicitly request or approve. Even when it seems helpful (verification scripts, patch pipelines, extra docs, npm scripts, workflow automation), unrequested additions create accidental complexity and maintenance debt for the user.

**Default rule**

- **Do not create** new files under `scripts/`, `docs/`, `.claude/`, or similar, unless the user explicitly asked for that artifact in the current task or approved it after you proposed it.
- **Do not extend** the repo with new automation (shell/PowerShell scripts, CI steps, `package.json` scripts) unless it is part of an agreed plan.
- **Prefer** solving the task with edits to existing files, inline commands, or a short explanation in chat.

**Before creating anything new**

1. State what you would add and why (one or two sentences).
2. Ask whether to proceed, or wait for explicit approval.
3. Implement only after a clear yes (or an explicit create/add request in the same message).

**Allowed without extra approval**

- Editing files the user already pointed at or that the task clearly requires.
- Fixing bugs in scripts/docs that **already exist** when the user asked to fix or use them.
- Mentioning a possible script or doc in the response **without** writing it.
<!-- </simplicity_first> -->

---

<!-- <surgical_changes> -->

## 4. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- Don't add fallbacks or unplanned features without explicitly asking the user first.

When your changes create orphans:

- Remove imports/variables/functions that YOUR changes made unused.

The test: Every changed line should trace directly to the user's request.

<!-- </surgical_changes> -->

---

<!-- <version_control> -->

## 5. Version Control

**Make every commit self-explanatory and descriptive.**

- The `conventional-commits` skill is the authority on commit message format and structure. Follow it.
<!-- </version_control> -->
