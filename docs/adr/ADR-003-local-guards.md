# ADR-003: Local forbidden-terms guard and gitleaks

- Status: accepted (M0, 2026-11-09)

## Context

Bricks start from reference implementations written for a specific organisation. Their names, hosts, table names
and similar identifiers must never reach this public repository (spec 2.1), and no secret may be committed
(spec 2.8). Publishing the list of forbidden names would itself reveal them.

## Decision

1. **Forbidden-terms guard** (`tools/guard/forbidden_terms.py`, standard library only):
   - Reads case-insensitive regular expressions, one per line, from `internal/forbidden-terms.txt`. The `internal/`
     folder is git-ignored and exists only on the maintainer's machine.
   - Scans file contents and file paths: staged content (pre-commit), all tracked files (pre-push), commit messages
     (commit-msg hook and, on pre-push, every outgoing commit's message and author/committer identity).
   - Prints only `file:line` and a masked match (`a****z`), never the patterns. Invalid patterns are reported by line
     number only.
   - If the list file is missing (any public clone, CI), it prints a notice and passes.
2. **gitleaks** for secrets:
   - Locally through the same hooks when the `gitleaks` binary is installed; otherwise the hook prints install
     instructions and continues (`AMEF_REQUIRE_GITLEAKS=1` makes it mandatory).
   - Always in CI (`gitleaks/gitleaks-action`, full history).
3. **Wiring:** `tools/guard/install_hooks.py` installs `pre-commit`, `commit-msg` and `pre-push` hooks that call
   `tools/guard/run_guards.py`. `.claude/settings.json` adds a Claude Code `PreToolUse` hook
   (`tools/guard/claude_hook.py`) that runs the same checks before any Bash `git commit` / `git push`, so an agent is
   stopped before git runs, with a readable message.
4. **Never rewrite history automatically.** If a forbidden term or secret is found in history, stop and ask the
   maintainer.

## Consequences

- The forbidden-terms check protects only clones that have the list; CI cannot run it. That is acceptable: only
  the maintainer's machine handles the reference code.
- Hooks can be bypassed with `--no-verify`; the Claude Code hook and the working agreement (`AGENTS.md`) forbid it.
- Generated reports must use relative paths, because local absolute paths can contain forbidden names.
