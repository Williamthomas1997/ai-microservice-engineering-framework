# Agent guide

Read before doing anything, in this order:

1. `docs/MASTER_SPEC.md`: the requirements. Authoritative.
2. `docs/IMPLEMENTATION_PLAN.md` and `docs/adr/`: the agreed architecture and decisions (written in M0, kept current).
3. `internal/NAMING.md` and `internal/REUSE_MAP.md` (local only, git-ignored): project identity, rename glossary,
   forbidden terms, and which source code to copy for each brick.
4. `internal/prompts/README.md` and the milestone prompt you were given (`internal/prompts/M<n>-PROMPT.md`).
5. The latest report in `docs/reports/`: what is actually done and what comes next.

If `internal/` is missing, you are in a public clone: follow `docs/` only.

## Working agreement

- Do only what the current milestone asks. Don't start later milestones.
- Follow `docs/IMPLEMENTATION_PLAN.md`. If something in a prompt or the plan is wrong in practice, choose the
  closest compliant option and record it as a **deviation** in the report. Never deviate silently.
- Write files only inside this project folder. Source repos named in `internal/REUSE_MAP.md` are **read-only**:
  only `git fetch` and `git archive` into a scratch folder outside this project, as described there.
- Copied code is renamed (`internal/NAMING.md` §2) and made generic before it is committed. Nothing in a commit may
  match `internal/forbidden-terms.txt`; the pre-commit/pre-push hook enforces it.
- No secrets in files, logs or commits. Config uses `${ENV}` placeholders; `.env.example` has placeholders only.
- No placeholder implementations or mocked core behaviour described as done. Unfinished = say so in the report.
- Single-owner rule (spec §2.2): never create a second Redis/Kafka/HTTP-client/tracing setup; use the brick.
- Every brick change covers **both** stacks (reactive first, then servlet) and the shared behaviour suite.
- Every app feature also adds QA artefacts in `qa/` (spec §8).
- Before finishing: run `mvn clean verify` from the root and fix failures. Paste the Maven summary and real
  surefire/failsafe counts in the report. Never claim a test passed if it did not run (Docker must be running for
  Testcontainers; if it isn't, start it or report it as blocked).
- From M1 on, run the `/review` pipeline over the milestone's diff and fix or justify every high finding.
- Update `README.md`, the relevant brick READMEs, manifests and ADRs in the same milestone.
- Finish with `docs/reports/M<n>-REPORT.md` (format below), then commit as
  `William Thomas <pkwilliamthomas@gmail.com>` (repo-local identity) with message `M<n>: <summary>`, and push to
  GitHub `origin main` only when everything above is green. Never push anywhere else.

## Report format (`docs/reports/M<n>-REPORT.md`)

1. Summary
2. Versions (anything new or changed)
3. Environment (OS, Java, Maven, Docker, versions of containers used by tests)
4. Files created / changed (tree)
5. Reuse log: source repo + commit hash → target module; copied / renamed / rewritten / dropped, and why
6. Tests: Maven summary lines, per-module test counts, ITs actually run
7. Review findings (`/review`): fixed / accepted with reason
8. Deviations from the plan or prompt, with reasons
9. Open items and recommended next step
