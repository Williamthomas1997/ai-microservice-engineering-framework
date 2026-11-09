# Implementation plan

The agreed plan for turning [`MASTER_SPEC.md`](MASTER_SPEC.md) into code. The spec is authoritative; this plan
records how we implement it. Decisions with alternatives live in [`adr/`](adr/). When a milestone changes a
decision, it updates this file in the same commit (and adds an ADR for anything new).

## 1. Identity

| Key | Value |
|---|---|
| Name | AI Microservice Engineering Framework (working name), short name `amef` |
| Maven groupId | `io.github.williamthomas1997` |
| Base Java package | `io.github.williamthomas1997.amef` |
| Artifacts | `amef-<module>` for foundation and apps, `amef-<brick>-{core,reactive,servlet}` for bricks |
| Config prefix | `amef.<brick>.*` (one prefix per brick) |
| Error codes | `AMEF-<BRICK>-<NNN>` (e.g. `AMEF-GW-001`), registry in `contracts` (M1) |
| Kafka topics | `amef.<domain>.<event>.v<N>`, always configurable |
| DB tables | default prefix `amef_`, configurable |
| Docker images | `amef/<app>` |
| Sample company | **Acme** (fictional) |

## 2. Versions

Java 21, Spring Boot 4.1.2, Spring Cloud 2025.1.4 (Gateway Server WebFlux 5.0.4), Jackson 3 (Boot default).
Every version, the reason for it and how it was verified: [ADR-000](adr/ADR-000-technology-versions.md).
Versions are managed in one place, `bom/pom.xml`.

## 3. Modules

| Folder | ArtifactId | Layer | Package | Milestone |
|---|---|---|---|---|
| `bom/` | `amef-bom` | L0 | - | M0 |
| `build-parent/` | `amef-build-parent` | L0 | - | M0 (guard wiring M1) |
| `platform/parent/` | `amef-platform-parent` (internal) | L0 | - | M0 |
| `platform/rules/` | `amef-platform-rules` (test-only, not published) | - | `...amef.platformrules` | M0 |
| `foundation/contracts/` | `amef-contracts` | L1 | `...amef.contracts` | M1 |
| `foundation/architecture-guard/` | `amef-architecture-guard` (+ test-jar) | L1 | `...amef.guard` | M1 |
| `foundation/test-support/` | `amef-test-support` | L1 | `...amef.testsupport` | M1 |
| `bricks/observability/{core,reactive,servlet}` | `amef-observability-*` | L2 | `...amef.observability.{core,reactive,servlet}` | M2 |
| `bricks/redis/...` | `amef-redis-*` | L3 | `...amef.redis.*` | M3 |
| `bricks/messaging/...` | `amef-messaging-*` | L3 | `...amef.messaging.*` | M4 |
| `bricks/resilience/...` | `amef-resilience-*` | L3 | `...amef.resilience.*` | M4 |
| `bricks/external-call/...` | `amef-external-call-*` | L4 | `...amef.externalcall.*` | M5 |
| `bricks/cache-sync/...` | `amef-cache-sync-*` | L4 | `...amef.cachesync.*` | M6 |
| `apps/gateway/` | `amef-gateway` | L5 | `...amef.gateway` | M7 |
| `apps/audit-service/` | `amef-audit-service` | L5 | `...amef.audit` | M8 |
| `apps/sample-service-reactive/` | `amef-sample-service-reactive` | L5 | `...amef.sample.reactive` | M8 |
| `apps/sample-service-servlet/` | `amef-sample-service-servlet` | L5 | `...amef.sample.servlet` | M8 |
| `qa/` (standalone, not in the reactor) | `amef-qa` | L5 | `...amef.qa` | M9 |

`...` = `io.github.williamthomas1997`. Layout rationale: [ADR-001](adr/ADR-001-module-layout-and-two-stacks.md).

### 3.1 POM hierarchy

```
amef-bom                       versions only (imports Boot, Cloud, Resilience4j, Allure BOMs; pins the rest)
└── amef-build-parent          consumers' parent: enforcer, compiler, Surefire/Failsafe, JaCoCo gate, guard
    ├── amef-platform-parent   platform modules: same build, but the banned-dependency rule is off
    │   └── foundation/*, bricks/*/*, apps/*, platform/rules
    └── amef-qa                standalone QA project
amef-root                      aggregator only (no inheritance)
```

Services either inherit `amef-build-parent` (recommended) or import `amef-bom`.

### 3.2 Manifests

Every module group has a manifest that tools and skills read (spec 3, "rules are data"):

- `bricks/<brick>/brick.yaml` (spec format plus `kind`, `description`, `package`, `status`, `milestone`);
- `foundation/<module>/module.yaml`, `apps/<app>/module.yaml`, `qa/module.yaml` (same schema, no `stacks`).

`python tools/manifests.py validate` checks: schema; layer range per kind; unique ids, packages (non-nested) and
artifacts; `requires` point to known modules on the same or a lower layer; no cycles; every declared artifact has a
`pom.xml`; every module is in the root reactor (except `qa`); intra-platform POM dependencies are covered by
`requires`; the build-parent enforcer bans equal the union of manifest `bans`. `generate` writes the catalogue in
`README.md` and the Mermaid graph in `docs/architecture.md`; CI runs `generate --check`. The compose profile list
(spec 3) is generated once `docker/` exists (M8).

## 4. Dependency and layer rules

- Layers (spec 2.3): L0 build → L1 foundation → L2 observability → L3 redis, messaging, resilience → L4
  external-call, cache-sync → L5 apps and qa. A module may depend on the same or a lower layer, never higher, never
  in a cycle.
- Enforced three ways: manifests (`tools/manifests.py validate`), POM dependencies (same tool), and bytecode
  (ArchUnit in `platform/rules`, reading layers and packages from the manifests; it includes a self-test proving it
  catches an upward dependency).
- Within a brick: `reactive` and `servlet` depend on `core`; `core` never depends on a web stack. A brick's
  `reactive` module may depend only on `reactive`/`core` modules of other bricks (same for `servlet`) - checked by
  the platform rules from M2 on.
- Single owner per concern (spec 2.2, [ADR-002](adr/ADR-002-single-owner-and-auto-config-ordering.md)): consumer
  services are banned (Maven Enforcer, direct dependencies) from adding the infrastructure libraries a brick owns.
  The platform's own apps (gateway, audit-service, samples) re-enable the same ban in their POMs, because they
  are consumers of the bricks too.

## 5. Auto-configuration conventions

Details and rationale in [ADR-002](adr/ADR-002-single-owner-and-auto-config-ordering.md).

- One `@AutoConfiguration` class per brick per stack, registered in
  `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`.
- Explicit ordering by layer: observability runs after Boot's observation/tracing auto-configs; L3 bricks run
  `after` observability; L4 `after` the L3 bricks they use. No `@AutoConfigureOrder` numbers.
- Every bean is `@ConditionalOnMissingBean`; every brick has `amef.<brick>.enabled` (default `true`) with documented
  fail-safe behaviour when disabled. Stack variants use `@ConditionalOnWebApplication(type = REACTIVE|SERVLET)` or
  class conditions so a `core` jar on the classpath alone creates no web beans.
- Properties are `@ConfigurationProperties` records; `spring-boot-configuration-processor` generates the metadata.

## 6. Package conventions

- Platform: `io.github.williamthomas1997.amef.<module>[.<stack>]` with sub-packages by role, e.g. `...redis.core.cache`,
  `...redis.reactive.autoconfigure`. Ports live in `contracts` (`...contracts.port`), with no Spring dependency.
- Services (enforced by architecture-guard, M1): `<base>.api`, `<base>.application`, `<base>.domain`,
  `<base>.infrastructure`. Business code depends on ports; adapters live in `infrastructure`.

## 7. Test strategy

| Kind | Where | Tooling | Runs in |
|---|---|---|---|
| Unit | every module | JUnit 6 (Boot-managed Jupiter), AssertJ | `test` (Surefire) |
| Behaviour suite | abstract tests in each brick's `-core` **test-jar**, extended in `-reactive` and `-servlet` | JUnit, test-support base classes | `test` |
| Integration (`*IT`) | modules with remote systems | Testcontainers (Redis, Kafka KRaft, Postgres), WireMock | `integration-test` (Failsafe) |
| Non-blocking | every reactive module | BlockHound (`-XX:+AllowRedefinitionToAddDeleteMethods` added by reactive modules) | `test` |
| Architecture | `platform/rules` (platform layering), architecture-guard test-jar (services) | ArchUnit | `test` |
| Python tools | `tools/tests` | pytest | CI, local |
| API / load | `qa/` against running services | Rest Assured, TestNG, Allure, Gatling | on demand, CI later |

Rules: ITs never skip silently when Docker is missing (they fail); reports quote real Surefire/Failsafe counts;
coverage gate on `application` + `domain` packages of services (default 70 %, `amef.coverage.minimum`).
`platform/rules` contains a Testcontainers smoke IT so every build proves the IT toolchain works.

## 8. Guards and CI

- Local: forbidden-terms check (pattern list kept outside the repository's tracked files) and gitleaks in git hooks
  (pre-commit, commit-msg, pre-push) and in a Claude Code PreToolUse hook. See
  [ADR-003](adr/ADR-003-local-guards.md).
- CI (`.github/workflows/build.yml`): JDK 21, `./mvnw -B clean verify` (Testcontainers on the Ubuntu runner),
  manifest validation, generated-docs check, pytest, gitleaks; Surefire/Failsafe reports uploaded. Dependabot for
  Maven, GitHub Actions and pip.
- Review agents (`.claude/agents/*`, `/review`): early version in M0, final in M10.

## 9. Milestones

| M | Scope | Stack work |
|---|---|---|
| M0 | Environment + versions, repo skeleton, build-parent/BOM, guards (forbidden terms, gitleaks), CI, review agents, first push | - |
| M1 | contracts + architecture-guard (proactive architecture util) | core + both error handlers |
| M2 | observability brick | reactive, then servlet |
| M3 | redis brick (port the existing starter, add reactive, streams queue) | reactive, then servlet |
| M4 | messaging (Kafka producer + consumer, outbox) + resilience bricks | reactive, then servlet |
| M5 | external-call brick (HTTP/SOAP/MQ, flow engine) | reactive, then servlet |
| M6 | cache-sync brick (back office) | reactive, then servlet |
| M7 | gateway app on the bricks | reactive |
| M8 | audit-service, sample services (both stacks), docker demo | both |
| M9 | QA automation suite + feature-to-QA rule wired into the workflow | - |
| M10 | AI layer: skills build system, pipelines, review agents (final), CLI, evals, PR review action | - |
| M11 | Docs site, README polish, release, make the repo public | - |

Scope notes carried forward from the M0 review:
- M1 (architecture-guard) also delivers: freeze mode (`FreezingArchRule`, switched by a build-parent property, store
  under the service's `src/test/resources`), and the owned-bean rule from ADR-002 (no bean of an owned
  infrastructure type defined outside its owner brick).
- Each brick milestone adds `test-jar` entries for its `amef-<brick>-core` behaviour suite to `amef-bom`.

Bricks start from reference implementations (copy, rename, then refactor to generic and to the single-owner rule
in the same milestone). A brick is not done while it contains organisation-specific logic, names, hosts or keys.

## 10. Risks

| Risk | Mitigation |
|---|---|
| Spring Boot 4 / Jackson 3 migration of reference code written for Boot 3 / Jackson 2 | Port per brick, compile against Boot 4.1 from the first commit; Jackson 2 only where a library forces it (e.g. shaded WireMock) |
| Spring Cloud train manages an older Resilience4j (2.3.0) than the Boot 4 module needs (2.4.0) | Resilience4j BOM imported before Spring Cloud in `amef-bom`; gateway circuit-breaker integration verified in M4/M7 (ADR-000) |
| Boot 4's OpenTelemetry starter exports OTLP metrics by default and logs connection errors without a collector | Observability brick (M2) defaults export off unless an endpoint is configured (spec 6.2 "works without a collector") |
| Spring Cloud 2026.0 (for Boot 4.2) is RC only | Stay on Boot 4.1 + Spring Cloud 2025.1.x; re-evaluate when 2026.0 is GA (Dependabot) |
| Testcontainers needs Docker; Windows and CI differ | Smoke IT in every build; Docker Desktop locally, Ubuntu runners in CI |
| Apps become Boot fat jars, which the platform-rules module cannot read as a library | App repackage uses a classifier (`exec`) so the plain jar stays a normal library (M7/M8) |
| Leaking organisation-specific names from reference code | Forbidden-terms guard in hooks (pre-commit, commit-msg, pre-push, Claude Code), review agents, ADR-003 |
| Stub modules make the layer rule vacuous today | Rule has a self-test with fixtures; it applies automatically as classes appear |
