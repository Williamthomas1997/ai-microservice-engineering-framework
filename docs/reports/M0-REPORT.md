# M0 report: environment, versions, skeleton, guards, CI, first push

## 1. Summary

M0 lays the foundations; there is no product code. Delivered:

- Versions chosen and verified (ADR-000): Java 21, Spring Boot 4.1.2, Spring Cloud 2025.1.4 (Gateway Server
  WebFlux 5.0.4), Jackson 3, plus pinned libraries. Two throwaway projects proved compatibility; both were deleted.
- `docs/IMPLEMENTATION_PLAN.md`, `docs/architecture.md`, ADR-000 to ADR-003.
- Maven skeleton: root aggregator, `amef-bom`, `amef-build-parent` (enforcer baseline + bans, Surefire/Failsafe,
  JaCoCo gate, guard property placeholder for M1), internal `amef-platform-parent`, 25 module stubs (3 foundation,
  6 bricks x core/reactive/servlet, 4 apps) with `package-info.java`, standalone `qa/` POM, Maven wrapper 3.9.16
  (SHA-256 pinned), `.gitattributes`, `.editorconfig`.
- Manifests: `brick.yaml` per brick, `module.yaml` for foundation, apps and qa. `tools/manifests.py validate|generate`
  with pytest tests; the README catalogue and the Mermaid graph are generated.
- `platform/rules`: ArchUnit layer rule driven by the manifests (with fixtures proving it detects an upward
  dependency) and a Testcontainers smoke IT.
- Guards: `tools/guard/forbidden_terms.py`, `run_guards.py`, `install_hooks.py` (pre-commit, commit-msg, pre-push),
  `claude_hook.py` merged into `.claude/settings.json` as a PreToolUse hook (existing permissions unchanged).
  Hooks installed and proven (see 6).
- CI `build.yml` (JDK 21 Temurin, Maven cache, manifests validate + generate --check, pytest, `./mvnw -B clean verify`,
  report upload, gitleaks job), `dependabot.yml`.
- Review agents (security, performance, architecture, test) + `/review` command; review run on M0 (see 7).
- README, LICENSE (Apache-2.0) + NOTICE (copyright William Thomas), CONTRIBUTING, SECURITY, CHANGELOG,
  `.env.example`, issue/PR templates. `START-HERE.md` deleted.

## 2. Versions

All new (first milestone). Full table with reasons: [ADR-000](../adr/ADR-000-technology-versions.md).

| Item | Version |
|---|---|
| Java | 21 |
| Spring Boot | 4.1.2 (Framework 7.0.10, Jackson 3.1.7, Micrometer 1.17.2, Tracing 1.7.2, OTel 1.62.0, Testcontainers 2.0.5, Caffeine 3.2.4, JUnit 6.0.3) |
| Spring Cloud | 2025.1.4 (Gateway 5.0.4) |
| Resilience4j | 2.4.0 (BOM imported before Spring Cloud) |
| ArchUnit / WireMock / BlockHound | 1.5.1 / 3.13.2 / 1.0.18.RELEASE |
| Velocity / MVEL / JEXL | 2.4.1 / 2.6.0.Final / 3.7.1 |
| Rest Assured / TestNG / Allure / Gatling | 6.3.0 / 7.12.0 / 3.1.1 / 3.16.0 (plugin 4.21.12) |
| JaCoCo plugin | 0.8.16 |
| Maven wrapper | Maven 3.9.16, wrapper 3.3.4 |
| jMolecules | evaluated only (2025.0.2), decision in M1 (ADR-004) |
| Python tools | PyYAML 6.0.3, pytest 9.2.0 |
| GitHub Actions | checkout v7, setup-java v6, setup-python v7, upload-artifact v7, gitleaks-action v3 |

## 3. Environment

| Item | Value |
|---|---|
| OS | Windows 11 Home Single Language 10.0.26200 (amd64) |
| Java | Oracle JDK 21.0.11 LTS |
| Maven | 3.9.11 installed; builds run through the wrapper (3.9.16) |
| Docker | Docker Desktop, Engine 29.4.1 (API 1.54), 16 CPUs, about 7.6 GB RAM |
| Python | 3.12.10 (project virtualenv `.venv`, git-ignored) |
| git | 2.45.1.windows.1 |
| gh | not installed |
| gitleaks | not installed locally (hooks print install hints; CI runs it) |
| Reachability | Maven Central OK (artifacts resolved), Docker Hub OK (`hello-world` pulled) |
| Containers used by tests | `redis:7.4-alpine` (smoke IT), `testcontainers/ryuk:0.14.0` |

## 4. Files created / changed

```
.claude/
  agents/{security,performance,architecture,test}-reviewer.md
  commands/review.md
  settings.json                     (hooks section merged; permissions unchanged)
.github/
  ISSUE_TEMPLATE/{bug_report.md, feature_request.md, config.yml}
  pull_request_template.md, dependabot.yml, workflows/build.yml
.mvn/wrapper/maven-wrapper.properties, mvnw, mvnw.cmd
.editorconfig, .env.example, .gitattributes, .gitignore (+ .pytest_cache)
README.md, LICENSE, NOTICE, CONTRIBUTING.md, SECURITY.md, CHANGELOG.md   (START-HERE.md deleted)
pom.xml                             root aggregator
bom/pom.xml                         amef-bom
build-parent/pom.xml                amef-build-parent
platform/parent/pom.xml             amef-platform-parent
platform/rules/                     pom.xml, LayerRule, LayerRuleTest, ModuleManifest, ToolchainSmokeIT, fixtures, logback-test.xml
foundation/{contracts,architecture-guard,test-support}/   pom.xml, module.yaml, package-info.java
bricks/{observability,redis,messaging,resilience,external-call,cache-sync}/
  brick.yaml, README.md, {core,reactive,servlet}/pom.xml + package-info.java
apps/{gateway,audit-service,sample-service-reactive,sample-service-servlet}/   pom.xml, module.yaml, package-info.java
qa/pom.xml, qa/module.yaml
tools/
  manifests.py, requirements.txt
  guard/{forbidden_terms.py, run_guards.py, install_hooks.py, claude_hook.py}
  tests/{test_manifests.py, test_guard.py}
docs/
  IMPLEMENTATION_PLAN.md, architecture.md
  adr/ADR-000..ADR-003
  reports/M0-REPORT.md, reports/reviews/2026-11-09-m0.md
```

## 5. Reuse log

None. M0 copies no code from the reference implementations (`internal/REUSE_MAP.md` starts in M1). The four agent
definitions, the guard scripts and the manifest tool were written new.

## 6. Tests

Maven (`./mvnw -B clean verify`, Docker running):

```
[INFO] Tests run: 5, Failures: 0, Errors: 0, Skipped: 0        (Surefire, amef-platform-rules: LayerRuleTest)
[INFO] Tests run: 1, Failures: 0, Errors: 0, Skipped: 0        (Failsafe, amef-platform-rules: ToolchainSmokeIT)
[INFO] Reactor Summary for AMEF :: root 0.1.0-SNAPSHOT: 30 modules SUCCESS
[INFO] BUILD SUCCESS
[INFO] Total time:  33.071 s
```

| Module | Surefire | Failsafe (ITs) |
|---|---|---|
| amef-platform-rules | 5 (LayerRuleTest: manifests present, packages do not overlap, platform has no upward dependency, rule reports an upward dependency, rule accepts downward dependencies) | 1 (ToolchainSmokeIT: real `redis:7.4-alpine` container via Testcontainers, PING → PONG) |
| all 25 stub modules, BOM, parents | 0 (no code yet) | 0 |

ITs actually run: 1 (ToolchainSmokeIT, container started and answered). The banned-dependency rule ran on the four
apps; it is off for bricks by design.

Other checks:
- `python -m pytest tools -q`: **39 passed** (manifests 15, guards 24).
- `python tools/manifests.py validate`: `manifests: OK (14 manifests)`; `generate --check`: up to date.
- `./mvnw -f qa/pom.xml verify`: BUILD SUCCESS (standalone QA POM resolves Rest Assured, TestNG, Allure, Gatling).
- `python tools/guard/install_hooks.py --check`: hooks installed and current.
- Hook proof: a temporary file containing a forbidden term was staged; `git hook run pre-commit` and a real
  `git commit` were both blocked (`guard-proof.txt:1: d****n`, exit 1); a commit message with a term was blocked by
  the commit-msg hook; the Claude hook, fed the same commit as JSON, returned exit 2. The file was then unstaged and
  deleted.

## 7. Review findings (`/review`)

Report: [`reviews/2026-11-09-m0.md`](reviews/2026-11-09-m0.md). high 0, medium 8, low 13.
Fixed: hook regex and `--no-verify` blocking, pre-push scan of outgoing commit content, bans re-enabled for apps,
BOM/README/platform-rules checks in `manifests.py`, missing guard tests, `-Xshare:off` removed, layer self-test
tightened, M1 scope notes (freeze mode, owned-bean rule). Accepted with reason: `.claude/settings.json`
permission breadth (medium) and deny gaps (low) need William's decision, because M0 was told to keep the
permissions unchanged; the remaining lows are deferred to the milestones listed in the review.

## 8. Deviations

1. **`platform/` folder** (`platform/parent`, `platform/rules`) is not named in spec 3. It holds the internal parent
   and the platform self-check module the prompt asks for; documented in ADR-001.
2. **`module.yaml` manifests** for foundation, apps and qa (spec 3 defines `brick.yaml` for bricks only), so the
   layer rule and the validator read every module's layer from data. Manifests carry extra fields (`kind`,
   `description`, `package`, `status`, `milestone`).
3. **Guard installer name** `install_hooks.py` (as in the M0 prompt), not `install-hooks.py` (spec 9.4), because
   Python modules cannot contain dashes.
4. **Toolchain smoke IT** added in `platform/rules`, so `verify` runs a real Testcontainers IT in M0 although there
   is no product code yet.
5. **LICENSE** is the verbatim Apache-2.0 text (keeps GitHub's licence detection); the copyright line
   "Copyright 2026 William Thomas" is in `NOTICE` and the README.
6. **Claude Code hook not active in this session:** settings are read when a session starts, so the PreToolUse hook
   was proven by feeding it JSON directly; the git hooks ran for the real commit.
7. **Compose profile list** (spec 3 generator output) is not generated yet: there is no `docker/` folder until M8.

## 9. Open items and next step

- **Decision for William:** tighten `.claude/settings.json` permissions (review findings 3 and 9): deny reads of
  `internal/**` and `.env`, deny edits to `tools/guard/**` and `.claude/settings.json`, deny force-push variants,
  and reconsider `python:*`, `powershell:*`, `curl:*` and unrestricted WebFetch in the allow list. Not changed in M0.
- **CI status:** `gh` is not installed, so the run could not be watched from here. Check it at
  https://github.com/Williamthomas1997/ai-microservice-engineering-framework/actions (or install `gh`, then run
  `gh auth login` and `gh run watch`).
- Install gitleaks locally (`winget install Gitleaks.Gitleaks`) so the hooks also scan for secrets.
- Guard auto-run in `amef-build-parent` is a documented placeholder until the rule pack exists (M1).
- Next: **M1** (contracts + architecture-guard, incl. freeze mode and owned-bean rule, ADR-004 jMolecules decision).
