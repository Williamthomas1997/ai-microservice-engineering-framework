---
description: Run the four AMEF review agents in parallel over a diff or path and write one merged, prioritised report.
argument-hint: "[base-ref | path] [scope-name]   (default: origin/main, scope from branch name)"
---

Review pipeline (spec 9.3). Arguments: `$ARGUMENTS`.

1. **Work out the scope.**
   - If the first argument is an existing path, the scope is that path (review the files under it).
   - Otherwise it is a git base ref (default `origin/main`; if that does not exist, the repository's first commit).
     The diff is `git diff <base>...HEAD` plus uncommitted changes (`git diff HEAD`) and untracked files
     (`git status --porcelain`).
   - Scope name for the report file: second argument, else the branch name, else the last path segment.
   - Print the scope in one line (`git diff --stat` summary or file count). If the scope is empty, stop.

2. **Run the four agents in parallel** (one message, four Task calls): `security-reviewer`,
   `performance-reviewer`, `architecture-reviewer`, `test-reviewer`. Give each the same scope description: the
   exact git range or path, and the list of changed files. Ask each to return findings in its documented format.

3. **Merge.** Collect all findings; drop exact duplicates (same file/line and issue), keeping the higher severity
   and noting all reporting agents. Sort high → medium → low, then by file.

4. **Write the report** to `docs/reports/reviews/<YYYY-MM-DD>-<scope-name>.md` (create the folder if needed):

   ```markdown
   # Review: <scope-name> (<YYYY-MM-DD>)

   Scope: <git range or path>, <n> files. Agents: security, performance, architecture, test.

   | # | Severity | Area | File | Issue | Fix | Status |
   |---|---|---|---|---|---|---|
   | 1 | high | security | path:line | ... | ... | open |

   ## Summary
   high: <n>, medium: <n>, low: <n>. Agents with no findings: <list>.
   ```

   `Status` starts as `open`. When a finding is fixed, set it to `fixed (<commit or short note>)`; when it is
   accepted, set it to `accepted: <reason>`. A milestone or PR is done only when no `high` is `open`.
   Use relative paths only, and never write a suspected secret or organisation name in full (mask it).

5. **Answer** with the report path and the counts per severity, then list the high findings (one line each).
   Do not fix anything unless the user asks.
