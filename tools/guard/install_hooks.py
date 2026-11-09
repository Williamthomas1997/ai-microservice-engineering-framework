#!/usr/bin/env python3
"""Installs the AMEF git hooks (pre-commit, commit-msg, pre-push) into this clone.

    python tools/guard/install_hooks.py           install or update the hooks
    python tools/guard/install_hooks.py --check   exit 1 if a hook is missing or outdated

Each hook calls tools/guard/run_guards.py (forbidden-terms check + gitleaks). An existing hook that was not
written by this installer is kept as <hook>.backup. Standard library only.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import stat
import subprocess
import sys

MARKER = "# Installed by tools/guard/install_hooks.py (AMEF)."
HOOKS = {
    "pre-commit": "pre-commit",
    "commit-msg": "commit-msg \"$1\"",
    "pre-push": "pre-push",
}
TEMPLATE = """#!/bin/sh
{marker} Do not edit: re-run the installer instead.
ROOT="$(git rev-parse --show-toplevel)" || exit 1
for candidate in python3 python py; do
  if command -v "$candidate" >/dev/null 2>&1 \\
     && "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >/dev/null 2>&1; then
    exec "$candidate" "$ROOT/tools/guard/run_guards.py" {args}
  fi
done
echo "AMEF guard: Python 3.9+ not found, cannot run the {name} hook." >&2
exit 1
"""


def hooks_dir() -> pathlib.Path:
    path = subprocess.run(["git", "rev-parse", "--git-path", "hooks"], capture_output=True, text=True, check=True)
    return pathlib.Path(path.stdout.strip()).resolve()


def render(name: str) -> str:
    return TEMPLATE.format(marker=MARKER, args=HOOKS[name], name=name)


def install(directory: pathlib.Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name in HOOKS:
        target = directory / name
        if target.exists() and MARKER not in target.read_text(encoding="utf-8", errors="replace"):
            backup = target.with_name(name + ".backup")
            target.replace(backup)
            print(f"kept existing {name} hook as {backup.name}")
        target.write_text(render(name), encoding="utf-8", newline="\n")
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"installed {name} hook")


def check(directory: pathlib.Path) -> int:
    problems = [name for name in HOOKS
                if not (directory / name).is_file()
                or (directory / name).read_text(encoding="utf-8", errors="replace") != render(name)]
    if problems:
        print(f"hooks missing or outdated: {', '.join(problems)}. Run: python tools/guard/install_hooks.py",
              file=sys.stderr)
        return 1
    print("hooks: installed and current")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install the AMEF git hooks.")
    parser.add_argument("--check", action="store_true", help="only verify that the hooks are installed")
    args = parser.parse_args(argv)
    os.chdir(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                            check=True).stdout.strip())
    directory = hooks_dir()
    if args.check:
        return check(directory)
    install(directory)
    return 0


if __name__ == "__main__":
    sys.exit(main())
