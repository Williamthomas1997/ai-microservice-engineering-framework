"""Tests for the local guards (tools/guard). They use a temporary pattern file, never the real list."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "guard"))

import claude_hook  # noqa: E402
import forbidden_terms  # noqa: E402
import install_hooks  # noqa: E402


def test_mask_hides_the_middle_of_a_match():
    assert forbidden_terms.mask("secretword") == "s********d"
    assert forbidden_terms.mask("ab") == "**"


def test_scan_text_is_case_insensitive_and_reports_line_numbers():
    patterns = [forbidden_terms.re.compile(r"\bglobex\b", forbidden_terms.re.IGNORECASE)]
    findings = forbidden_terms.scan_text("f.txt", "ok\nGlobex corp\n", patterns)
    assert findings == ["f.txt:2: G****x"]


def test_outgoing_ranges_from_pre_push_input():
    zero = forbidden_terms.ZERO_SHA
    stdin = f"refs/heads/main {'a' * 40} refs/heads/main {'b' * 40}\nrefs/heads/new {'c' * 40} refs/heads/new {zero}\n" \
            f"(delete) {zero} refs/heads/old {'d' * 40}\n"
    assert forbidden_terms.outgoing_rev_args(stdin) == [
        [f"{'b' * 40}..{'a' * 40}"], ["c" * 40, "--not", "--remotes"]]


@pytest.mark.parametrize("command,expected", [
    ("git commit -m 'x'", {"commit"}),
    ("git -C repo push origin main", {"push"}),
    ("git add -A && git commit -m x && git push", {"commit", "push"}),
    ("git status", set()),
    ("echo git-commit", set()),
    ("git --no-pager commit -m x", {"commit"}),
    ("git --git-dir=.git push", {"push"}),
    ("git -P push origin main", {"push"}),
])
def test_claude_hook_detects_git_commit_and_push(command, expected):
    assert claude_hook.git_actions(command) == expected


def test_claude_hook_extracts_inline_messages():
    assert claude_hook.inline_messages('git commit -m "M0: first" --message=second') == ["M0: first", "second"]


@pytest.fixture
def git_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    def run(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)
    run("init", "-q", "-b", "main")
    run("config", "user.name", "Test")
    run("config", "user.email", "test@example.invalid")
    return tmp_path


def _guard(repo: pathlib.Path, *args: str) -> subprocess.CompletedProcess:
    script = pathlib.Path(forbidden_terms.__file__)
    return subprocess.run([sys.executable, str(script), *args], cwd=repo, capture_output=True, text=True)


def test_staged_file_with_forbidden_term_is_blocked_and_pattern_is_not_printed(git_repo, tmp_path_factory):
    patterns = tmp_path_factory.mktemp("p") / "terms.txt"
    patterns.write_text("globex\n", encoding="utf-8")
    (git_repo / "a.txt").write_text("hello\nwe work for GLOBEX\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], cwd=git_repo, check=True)

    result = _guard(git_repo, "--staged", "--patterns", str(patterns))

    assert result.returncode == 1
    assert "a.txt:2: G****X" in result.stderr
    assert "globex" not in (result.stdout + result.stderr).lower()


def test_clean_staged_file_passes(git_repo, tmp_path_factory):
    patterns = tmp_path_factory.mktemp("p") / "terms.txt"
    patterns.write_text("globex\n", encoding="utf-8")
    (git_repo / "a.txt").write_text("Acme only\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], cwd=git_repo, check=True)

    assert _guard(git_repo, "--staged", "--patterns", str(patterns)).returncode == 0


def test_missing_pattern_file_skips_with_notice(git_repo):
    result = _guard(git_repo, "--all")
    assert result.returncode == 0
    assert "check skipped" in result.stdout


def test_commit_message_file_is_checked(git_repo, tmp_path_factory):
    patterns = tmp_path_factory.mktemp("p") / "terms.txt"
    patterns.write_text("globex\n", encoding="utf-8")
    message = git_repo / "MSG"
    message.write_text("M1: add globex client\n# globex in a comment line is ignored\n", encoding="utf-8")

    result = _guard(git_repo, "--message-file", str(message), "--patterns", str(patterns))

    assert result.returncode == 1
    assert "commit message:1:" in result.stderr


HOOK = pathlib.Path(claude_hook.__file__)


def _hook(repo: pathlib.Path, stdin: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(HOOK)], cwd=repo, input=stdin, capture_output=True, text=True)


@pytest.mark.parametrize("command", [
    "git commit --no-verify -m x",
    "git push --no-verify",
    "git -c core.hooksPath=/dev/null commit -m x",
    "git commit -n -m x",
])
def test_claude_hook_blocks_hook_bypass(git_repo, command):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    assert _hook(git_repo, payload).returncode == 2


def test_claude_hook_passes_other_commands_and_blocks_invalid_input(git_repo):
    assert _hook(git_repo, json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}})).returncode == 0
    assert _hook(git_repo, json.dumps({"tool_name": "Read", "tool_input": {}})).returncode == 0
    assert _hook(git_repo, "not json").returncode == 2


def test_claude_hook_blocks_commit_with_forbidden_term(git_repo):
    (git_repo / "internal").mkdir()
    (git_repo / "internal/forbidden-terms.txt").write_text("globex\n", encoding="utf-8")
    (git_repo / "a.txt").write_text("GLOBEX\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], cwd=git_repo, check=True)
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git commit -m ok"}})

    result = _hook(git_repo, payload)

    assert result.returncode == 2
    assert "a.txt:1: G****X" in result.stderr


def test_pre_push_scans_content_of_outgoing_commits_even_if_removed_later(git_repo):
    def run(*args):
        subprocess.run(["git", *args], cwd=git_repo, check=True, capture_output=True)
    (git_repo / "a.txt").write_text("globex\n", encoding="utf-8")
    run("add", "a.txt"); run("commit", "-q", "-m", "one")
    (git_repo / "a.txt").write_text("clean\n", encoding="utf-8")
    run("commit", "-q", "-am", "two")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=git_repo, capture_output=True, text=True).stdout.strip()
    patterns = git_repo.parent / "terms.txt"
    patterns.write_text("globex\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(pathlib.Path(forbidden_terms.__file__)), "--pre-push", "--patterns", str(patterns)],
        cwd=git_repo, input=f"refs/heads/main {head} refs/heads/main {forbidden_terms.ZERO_SHA}\n",
        capture_output=True, text=True)

    assert result.returncode == 1
    assert "a.txt:1: g****x" in result.stderr


def test_install_hooks_keeps_foreign_hook_and_check_detects_drift(git_repo, monkeypatch):
    monkeypatch.chdir(git_repo)
    hooks = install_hooks.hooks_dir()
    hooks.mkdir(parents=True, exist_ok=True)
    (hooks / "pre-commit").write_text("#!/bin/sh\necho mine\n", encoding="utf-8")

    install_hooks.install(hooks)

    assert (hooks / "pre-commit.backup").read_text(encoding="utf-8") == "#!/bin/sh\necho mine\n"
    assert install_hooks.check(hooks) == 0
    (hooks / "pre-push").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    assert install_hooks.check(hooks) == 1
