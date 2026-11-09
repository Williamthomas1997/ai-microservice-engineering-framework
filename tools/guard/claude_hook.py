#!/usr/bin/env python3
"""Claude Code PreToolUse hook: runs the local guards before a Bash `git commit` or `git push`.

Configured in .claude/settings.json (hooks.PreToolUse, matcher "Bash"). Reads the hook JSON from stdin.
- git commit: forbidden-terms over staged changes and over any -m/--message text, plus gitleaks on staged changes.
- git push:   forbidden-terms over all tracked files and the messages of commits not yet on any remote,
              plus gitleaks over those commits.
Exit 2 blocks the tool call and shows stderr to Claude; exit 0 lets it run. The git hooks installed by
install_hooks.py run the same checks again inside git, so this hook is an early, visible first line.
"""
from __future__ import annotations

import io
import json
import os
import re
import shlex
import sys
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import forbidden_terms  # noqa: E402
import run_guards  # noqa: E402

# `git`, then any global options (`-c k=v`, `-C dir`, `--no-pager`, `--git-dir=x`, `-P`, ...), then the sub-command.
GIT_ACTION = re.compile(
    r"(?:^|[;&|(]\s*|\s)git(?:\s+(?:-[cC]\s+\S+|--?[\w-]+(?:=\S+)?))*\s+(commit|push)\b")
# Ways to skip the git hooks; agents must never use them (AGENTS.md).
HOOK_BYPASS = re.compile(r"--no-verify\b|core\.hooksPath|\bcommit\b[^;&|]*\s-n\b")


def git_actions(command: str) -> set[str]:
    return {match.group(1) for match in GIT_ACTION.finditer(command)}


def inline_messages(command: str) -> list[str]:
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return []
    messages = []
    for index, token in enumerate(tokens):
        if token in ("-m", "--message") and index + 1 < len(tokens):
            messages.append(tokens[index + 1])
        elif token.startswith("--message="):
            messages.append(token.split("=", 1)[1])
    return messages


def run_quietly(function, *args) -> tuple[int, str]:
    buffer = io.StringIO()
    with redirect_stdout(buffer), redirect_stderr(buffer):
        try:
            status = function(*args)
        except SystemExit as exit_:
            status = exit_.code if isinstance(exit_.code, int) else 1
        except Exception as error:  # a broken guard must block, not silently pass
            print(f"guard error: {error}")
            status = 1
    return status, buffer.getvalue()


def check_commit(command: str) -> tuple[int, str]:
    status, output = run_quietly(run_guards.pre_commit)
    root = forbidden_terms.repo_root()
    pattern_file = root / forbidden_terms.PATTERNS_RELATIVE
    if pattern_file.is_file():
        patterns = forbidden_terms.load_patterns(pattern_file)
        findings = [f for text in inline_messages(command)
                    for f in forbidden_terms.scan_text("commit message", text, patterns)]
        message_status, message_output = run_quietly(forbidden_terms.report, findings, "commit message")
        status, output = max(status, message_status), output + message_output
    return status, output


def check_push() -> tuple[int, str]:
    head = forbidden_terms.git("rev-parse", "HEAD").strip()
    simulated_stdin = f"HEAD {head} refs/heads/unknown {forbidden_terms.ZERO_SHA}\n"
    return run_quietly(run_guards.pre_push, simulated_stdin)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("AMEF guard: hook input is not valid JSON; blocking to stay safe.", file=sys.stderr)
        return 2
    if payload.get("tool_name") != "Bash":
        return 0
    command = str(payload.get("tool_input", {}).get("command", ""))
    actions = git_actions(command)
    if not actions:
        return 0
    if HOOK_BYPASS.search(command):
        print("AMEF guard blocked this git command: skipping the git hooks (--no-verify, -n, core.hooksPath) "
              "is not allowed.", file=sys.stderr)
        return 2

    status, output = 0, ""
    try:
        if "commit" in actions:
            s, o = check_commit(command)
            status, output = max(status, s), output + o
        if "push" in actions:
            s, o = check_push()
            status, output = max(status, s), output + o
    except Exception as error:  # a broken guard must block, not silently pass
        status, output = 1, output + f"guard error: {error}\n"
    if status != 0:
        print("AMEF guard blocked this git command:\n" + output, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
