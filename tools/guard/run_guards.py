#!/usr/bin/env python3
"""Runs the local guards for one git hook stage: the forbidden-terms check and gitleaks.

    python tools/guard/run_guards.py pre-commit
    python tools/guard/run_guards.py commit-msg <message-file>
    python tools/guard/run_guards.py pre-push            (reads the pre-push hook stdin)

gitleaks is optional locally: if it is not installed, a notice explains how to install it and the stage continues
(CI always runs gitleaks). Set AMEF_REQUIRE_GITLEAKS=1 to make a missing gitleaks binary fail the stage.
Standard library only. Exit code 0 = pass, 1 = blocked.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import forbidden_terms  # noqa: E402

INSTALL_HINT = (
    "gitleaks: not installed; secret scan skipped locally (CI still runs it). Install it with one of:\n"
    "  winget install Gitleaks.Gitleaks   |   brew install gitleaks   |   "
    "https://github.com/gitleaks/gitleaks/releases"
)


def gitleaks(args: list[str]) -> int:
    binary = shutil.which("gitleaks")
    if binary is None:
        print(INSTALL_HINT)
        return 1 if os.environ.get("AMEF_REQUIRE_GITLEAKS") == "1" else 0
    # gitleaks >= 8.19 has the `git` sub-command; older versions use protect/detect.
    modern = subprocess.run([binary, "git", "--help"], capture_output=True).returncode == 0
    if modern:
        command = [binary, "git", "--redact", "--no-banner", *args]
    elif "--staged" in args:
        command = [binary, "protect", "--staged", "--redact", "--no-banner"]
    else:
        command = [binary, "detect", "--redact", "--no-banner", *args]
    result = subprocess.run(command)
    if result.returncode != 0:
        print("gitleaks: possible secret found (see above). Remove it before committing/pushing.", file=sys.stderr)
        return 1
    print("gitleaks: OK")
    return 0


def pre_commit() -> int:
    status = forbidden_terms.main(["--staged"])
    return max(status, gitleaks(["--staged"]))


def commit_msg(message_file: str) -> int:
    return forbidden_terms.main(["--message-file", message_file])


def pre_push(stdin_text: str) -> int:
    root = forbidden_terms.repo_root()
    pattern_file = root / forbidden_terms.PATTERNS_RELATIVE
    status = 0
    if pattern_file.is_file():
        patterns = forbidden_terms.load_patterns(pattern_file)
        findings = forbidden_terms.scan_tracked(root, patterns)
        for rev_args in forbidden_terms.outgoing_rev_args(stdin_text):
            findings.extend(forbidden_terms.scan_commit_messages(root, rev_args, patterns))
        status = forbidden_terms.report(findings, "tracked files and outgoing commits")
    else:
        print(f"forbidden-terms: {forbidden_terms.PATTERNS_RELATIVE.as_posix()} not found; check skipped.")
    for rev_args in forbidden_terms.outgoing_rev_args(stdin_text):
        status = max(status, gitleaks([f"--log-opts={' '.join(rev_args)}"]))
    return status


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in {"pre-commit", "commit-msg", "pre-push"}:
        print(__doc__, file=sys.stderr)
        return 2
    stage = argv[0]
    if stage == "pre-commit":
        return pre_commit()
    if stage == "commit-msg":
        if len(argv) != 2:
            print("usage: run_guards.py commit-msg <message-file>", file=sys.stderr)
            return 2
        return commit_msg(argv[1])
    return pre_push(sys.stdin.read())


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
