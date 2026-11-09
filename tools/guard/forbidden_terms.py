#!/usr/bin/env python3
"""Forbidden-terms guard (local only, see docs/adr/ADR-003-local-guards.md).

Reads one case-insensitive regular expression per line from `internal/forbidden-terms.txt` (git-ignored, so
the public repository never shows the list) and fails when any of them matches. It never prints the patterns,
only `file:line` and a masked form of the match.

Modes:
    --staged                 staged content of every staged file, plus the staged paths (pre-commit)
    --all                    every tracked file in the working tree, plus the tracked paths
    --message-file FILE      a commit message file (commit-msg hook)
    --commits RANGE          messages of the commits in a git revision range, e.g. origin/main..HEAD
    --pre-push               read the pre-push hook's stdin and check all tracked files plus the messages,
                             identities and added lines of every outgoing commit

If the pattern file is missing (a public clone), the check prints a notice and passes.
Standard library only, so the git hooks need no virtualenv. Exit codes: 0 clean or skipped, 1 match, 2 usage.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

PATTERNS_RELATIVE = pathlib.Path("internal") / "forbidden-terms.txt"
ZERO_SHA = "0" * 40
MAX_FILE_BYTES = 5 * 1024 * 1024


def git(*args: str, root: pathlib.Path | None = None, binary: bool = False):
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, check=True)
    return result.stdout if binary else result.stdout.decode("utf-8", errors="replace")


def repo_root() -> pathlib.Path:
    return pathlib.Path(git("rev-parse", "--show-toplevel").strip())


def load_patterns(path: pathlib.Path) -> list[re.Pattern[str]]:
    patterns = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            patterns.append(re.compile(line, re.IGNORECASE))
        except re.error as error:
            # Report the line number only: printing the pattern would reveal the list.
            raise SystemExit(f"forbidden-terms: invalid regular expression on line {number} of {path.name}: {error.msg}")
    return patterns


def mask(text: str) -> str:
    if len(text) <= 2:
        return "*" * len(text)
    return f"{text[0]}{'*' * (len(text) - 2)}{text[-1]}"


def scan_text(label: str, text: str, patterns: list[re.Pattern[str]]) -> list[str]:
    findings = []
    for number, line in enumerate(text.splitlines(), start=1):
        for pattern in patterns:
            for match in pattern.finditer(line):
                findings.append(f"{label}:{number}: {mask(match.group(0))}")
    return findings


def decode(blob: bytes) -> str | None:
    """Text content, or None for binary/oversized blobs (not scanned)."""
    if len(blob) > MAX_FILE_BYTES or b"\0" in blob[:8192]:
        return None
    return blob.decode("utf-8", errors="replace")


def scan_paths(paths: list[str], patterns) -> list[str]:
    return [f"(path) {path}: {mask(m.group(0))}" for path in paths for p in patterns for m in p.finditer(path)]


def scan_staged(root: pathlib.Path, patterns) -> list[str]:
    paths = [p for p in git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z", root=root).split("\0") if p]
    findings = scan_paths(paths, patterns)
    for path in paths:
        text = decode(git("show", f":{path}", root=root, binary=True))
        if text is not None:
            findings.extend(scan_text(path, text, patterns))
    return findings


def scan_tracked(root: pathlib.Path, patterns) -> list[str]:
    paths = [p for p in git("ls-files", "-z", root=root).split("\0") if p]
    findings = scan_paths(paths, patterns)
    for path in paths:
        file = root / path
        if not file.is_file():
            continue  # deleted in the working tree but still tracked
        text = decode(file.read_bytes())
        if text is not None:
            findings.extend(scan_text(path, text, patterns))
    return findings


def scan_commit_messages(root: pathlib.Path, rev_args: list[str], patterns) -> list[str]:
    findings = []
    shas = [s for s in git("rev-list", *rev_args, root=root).split() if s]
    for sha in shas:
        message = git("log", "-1", "--format=%B", sha, root=root)
        findings.extend(scan_text(f"commit {sha[:10]} message", message, patterns))
        author = git("log", "-1", "--format=%an <%ae>%n%cn <%ce>", sha, root=root)
        findings.extend(scan_text(f"commit {sha[:10]} identity", author, patterns))
        findings.extend(scan_commit_content(root, sha, patterns))
    return findings


def scan_commit_content(root: pathlib.Path, sha: str, patterns) -> list[str]:
    """Lines added by one commit (and the paths it touches). Catches a term that a later commit removed again,
    which a scan of the working tree alone would miss but which would still be published in history."""
    findings = []
    patch = git("show", "--format=", "--no-color", "--unified=0", "--no-ext-diff", "--text", sha, root=root)
    current = "?"
    for line in patch.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else line[4:]
            findings.extend(scan_paths([current], patterns))
        elif line.startswith("+") and not line.startswith("+++"):
            findings.extend(f"commit {sha[:10]} {f}" for f in scan_text(current, line[1:], patterns))
    return findings


def outgoing_rev_args(stdin_text: str) -> list[list[str]]:
    """Revision ranges for the pre-push hook input lines: `<local ref> <local sha> <remote ref> <remote sha>`."""
    ranges = []
    for line in stdin_text.splitlines():
        parts = line.split()
        if len(parts) != 4 or parts[1] == ZERO_SHA:
            continue  # malformed or a branch deletion
        local_sha, remote_sha = parts[1], parts[3]
        if remote_sha == ZERO_SHA:
            ranges.append([local_sha, "--not", "--remotes"])  # new branch: everything not on any remote yet
        else:
            ranges.append([f"{remote_sha}..{local_sha}"])
    return ranges


def report(findings: list[str], what: str) -> int:
    if not findings:
        print(f"forbidden-terms: OK ({what})")
        return 0
    print(f"forbidden-terms: {len(findings)} match(es) in {what}. Remove them before committing/pushing:",
          file=sys.stderr)
    for finding in findings[:200]:
        print(f"  {finding}", file=sys.stderr)
    if len(findings) > 200:
        print(f"  ... and {len(findings) - 200} more", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail when a forbidden term appears in files or commit messages.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--staged", action="store_true")
    group.add_argument("--all", action="store_true")
    group.add_argument("--message-file", type=pathlib.Path)
    group.add_argument("--commits", metavar="RANGE")
    group.add_argument("--pre-push", action="store_true")
    parser.add_argument("--patterns", type=pathlib.Path, help="pattern file (default: internal/forbidden-terms.txt)")
    args = parser.parse_args(argv)

    root = repo_root()
    pattern_file = args.patterns or root / PATTERNS_RELATIVE
    if not pattern_file.is_file():
        print(f"forbidden-terms: {PATTERNS_RELATIVE.as_posix()} not found; check skipped (expected in a public clone).")
        return 0
    patterns = load_patterns(pattern_file)
    if not patterns:
        print("forbidden-terms: pattern file is empty; check skipped.")
        return 0

    if args.staged:
        return report(scan_staged(root, patterns), "staged changes")
    if args.all:
        return report(scan_tracked(root, patterns), "tracked files")
    if args.message_file:
        text = args.message_file.read_text(encoding="utf-8", errors="replace")
        text = "\n".join(line for line in text.splitlines() if not line.startswith("#"))
        return report(scan_text("commit message", text, patterns), "commit message")
    if args.commits:
        return report(scan_commit_messages(root, [args.commits], patterns), f"commits {args.commits}")

    findings = scan_tracked(root, patterns)
    for rev_args in outgoing_rev_args(sys.stdin.read()):
        findings.extend(scan_commit_messages(root, rev_args, patterns))
    return report(findings, "tracked files and outgoing commits")


if __name__ == "__main__":
    sys.exit(main())
