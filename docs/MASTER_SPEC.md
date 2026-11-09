# AI Microservice Engineering Framework: master specification

Working name. The short name (`amef`), packages and prefixes are defined once in the local naming file and
applied in M0.

## 1. What this is

An open-source framework for building production-grade Spring Boot microservices **by prompting**. It has
three parts that only work well together:

1. **Bricks:** reusable Spring Boot starters (logging and tracing, Redis, Kafka, resilience, external calls,
   cache sync, contracts, architecture guard). Every brick ships a **reactive** (WebFlux) and a **servlet**
   (Spring MVC) variant over a shared core.
2. **Templates and apps:** a gateway, an audit service, reference sample services in both stacks, and a QA
   automation suite. Users start new projects from these.
3. **AI layer:** Claude Code skills, review agents and Python tools that add features, create bricks, compose
   services, write tests and review code, while deterministic tooling enforces the rules.

The point is to spend AI tokens on business logic only. Structure, infrastructure, tests and quality gates come
from the framework.

Out of scope: project memory / knowledge graph (a separate project; the README links to it), environment
release pipelines of any specific company, business rules of any specific company.

## 2. Non-negotiable principles

1. **Generic only.** No business rules, customer data, company names, hosts, keys or table names that belong
   to a real organisation. Anything domain-like is configuration, a port, or a plug-in that is off by default.
   Samples use the fictional company **Acme**.
2. **Single owner per concern.** Exactly one brick creates each infrastructure bean:
   observability owns MDC/tracing/log format; redis owns Redis connections and templates; messaging owns Kafka
   producers/consumers; resilience owns Resilience4j registries; external-call owns outbound HTTP/MQ clients.
   No brick, app or service creates its own copy. Gateway caching, rate limiting, logging and audit go through
   the bricks too.
3. **Layered, downward-only dependencies** (enforced by ArchUnit in this repo):
   `L0 build` → `L1 contracts, architecture-guard` → `L2 observability` → `L3 redis, messaging, resilience` →
   `L4 external-call, cache-sync` → `L5 apps (gateway, audit-service, sample services) and qa`.
4. **Two stacks, one behaviour.** Each brick = `-core` + `-reactive` + `-servlet`. A behavioural test suite in
   `-core` (test-jar) runs against both variants. A reactive module must never block a Netty event-loop thread
   (BlockHound in reactive tests).
5. **Replaceable by design.** Auto-configuration with `@ConditionalOnMissingBean`, explicit
   `@AutoConfiguration(after/before)` ordering, one config prefix per brick (`amef.<brick>.*`), and
   `spring-configuration-metadata.json` generated for every property.
6. **Ports and adapters.** Business code depends on ports (interfaces). Infrastructure lives in adapters. Data
   access goes through a port so it can be cached later by decorating the adapter with the redis brick.
7. **Fail safe.** Infrastructure outages degrade, they don't break requests where the spec says so (Redis
   disabled → pass-through; Kafka down → outbox), and every degradation is logged and counted.
8. **No secrets anywhere.** Configuration uses `${ENV}` placeholders. `.env.example` has placeholders only.
   gitleaks runs locally and in CI.
9. **Everything tested for real.** Testcontainers for Redis, Kafka, Postgres; WireMock for external systems.
   No mocked core behaviour reported as done.

## 3. Repository layout

```
<repo>/
├── bom/                         versions for consumers (bricks + third-party)
├── build-parent/                parent POM for services: enforcer bans, JaCoCo gate, guard auto-run, plugins
├── foundation/
│   ├── contracts/               ports, annotations, response/error model, event + audit schema
│   ├── architecture-guard/      ArchUnit rule pack (test-jar)
│   └── test-support/            shared Testcontainers setup, behaviour-suite base classes, BlockHound setup
├── bricks/
│   ├── observability/   {core, reactive, servlet}
│   ├── redis/           {core, reactive, servlet}
│   ├── messaging/       {core, reactive, servlet}
│   ├── resilience/      {core, reactive, servlet}
│   ├── external-call/   {core, reactive, servlet}
│   └── cache-sync/      {core, reactive, servlet}
├── apps/
│   ├── gateway/                 reactive (servlet variant later, optional)
│   ├── audit-service/
│   ├── sample-service-reactive/
│   └── sample-service-servlet/
├── qa/                          API automation (Rest Assured, TestNG, Allure) + load (Gatling)
├── ai/                          skill sources, building-block notes, agent definitions, evals
├── tools/                       Python: CLI, skill builder, guards, generators
├── docker/                      compose profiles, observability stack, WireMock mappings
├── docs/                        this spec, implementation plan, ADRs, brick guides, reports
├── .claude/                     generated skills, agents, commands, hooks (built from ai/)
└── .github/workflows/           CI
```

Each brick folder has a `README.md` (fixed layout, §11) and a `brick.yaml` manifest:

```yaml
id: redis
layer: 3
stacks: [reactive, servlet]
artifacts: { core: amef-redis-core, reactive: amef-redis-reactive, servlet: amef-redis-servlet }
provides: [CachePort, LockPort, IdempotencyPort, InvalidationBus, StreamQueue]
requires: [contracts, observability]
infra: [redis]
bans: [spring-boot-starter-data-redis, spring-boot-starter-data-redis-reactive]
config-prefix: amef.redis
```

`tools/` validates all manifests (layering, cycles, artifacts exist) and generates the catalogue table in the
root README, the dependency graph (Mermaid) and the compose profile list.

## 4. Versions

Java 21 (LTS) baseline. Latest GA Spring Boot and the matching Spring Cloud release train that supports
Spring Cloud Gateway (verified in M0, recorded in ADR-000). Testcontainers, ArchUnit, Resilience4j, Micrometer
Tracing (OTel bridge) at versions managed by Boot or pinned in the BOM.

## 5. Foundation

### 5.1 contracts
- Annotations: `@Port`, `@Adapter`, `@UseCase` (or jMolecules equivalents if adopted, see ADR).
- One response model: `ApiResponse<T>` + `ErrorEnvelope` (code, message, category, traceId, details), error-code
  registry (`AMEF-<BRICK>-NNN`), `ErrorCatalog` port for message lookup (i18n bundle adapter by default, DB
  adapter optional), servlet and reactive error handlers that map exceptions to the envelope.
- `EventEnvelope` (eventId, type, version, occurredAt, traceId, subjectId, payload) and `AuditEvent` (gateway
  request logs and external-call audit share it).
- Ports: `CachePort`, `LockPort`, `IdempotencyPort`, `EventPublisher`, `ExternalCallPort`, `AuditSink`,
  `ErrorCatalog`, `IdGenerator`, `ClockPort`.

### 5.2 architecture-guard (proactive architecture enforcement)
- Packaged as a test-jar. The build-parent runs it in every service's `mvn test` (Surefire
  `dependenciesToScan`); the service only sets `amef.guard.base-package`.
- Package convention: `api`, `application`, `domain`, `infrastructure`.
- Rules: `application`/`domain` never import persistence, HTTP client, Kafka or Redis types; infrastructure
  classes that touch DB/external systems are `@Adapter`s implementing a `@Port`; controllers call only
  `application`; no field injection; no `System.out`/`printStackTrace`; every `@UseCase`/application service has
  a unit test class; naming conventions; no cycles between packages.
- Build-parent: Maven Enforcer bans direct infrastructure starters (services must use bricks); JaCoCo minimum
  line coverage on `application` + `domain` (default 70%, configurable); freeze mode (ArchUnit `FreezingArchRule`)
  for adopting the guard in existing code.
- This repo applies the same guard to its own sample services, and a separate rule set to the bricks themselves
  (layer order from §2.3).

## 6. Bricks

### 6.1 Common requirements
Auto-config per stack; properties with metadata; actuator health indicator where there is a remote system;
Micrometer metrics; behavioural test suite run against both stacks; a runnable example in the README;
`brick.yaml`.

### 6.2 observability (L2)
- Micrometer Tracing (OTel bridge) for traceId/spanId and propagation (W3C `traceparent`) on HTTP clients built
  from Boot builders, Kafka (observation enabled), `@Async`/executors (context-propagating task decorator) and
  Reactor (automatic context propagation).
- Baggage for identity fields (configurable list, default `userId`, `subjectId`, `channel`), copied into MDC.
- Request context filter (servlet `OncePerRequestFilter`, reactive `WebFilter`): resolves identity fields from
  configurable headers/claims, sets MDC, adds `endpoint`/`handler`, logs request summary.
- Legacy header bridge: configurable list of header names to read and to write on outbound calls
  (for downstream systems that expect non-W3C headers).
- Masking engine: field-name and regex rules from config; applied to log bodies and audit payloads; `@Sensitive`
  annotation for DTO fields.
- Body logging per path pattern, with size limit, off by default.
- Structured JSON logs (Boot's built-in structured logging), console pattern for local profile.
- `@Loggable` aspect for method timing.
- Optional OTLP export; works without a collector.

### 6.3 redis (L3)
- Annotation caching with a per-call `CachePolicy` (L1 Caffeine and/or L2 Redis, TTLs, null caching, lock on
  miss, timeout action), eviction after commit, generation (version-bump) invalidation, pub/sub invalidation bus
  that clears L1 on every pod. Reactive: works with `Mono`/`Flux` return types and offers a programmatic API.
- Distributed lock (annotation + service, renewal, fencing-safe unlock), rate limiter (token bucket, Lua),
  idempotency (annotation + HTTP `Idempotency-Key` filter), sequences, Redis Streams queue (consumer groups, ack,
  pending-claim).
- Implements `CachePort`, `LockPort`, `IdempotencyPort`.
- `amef.redis.enabled=false` → caching becomes pass-through, locks fall back to local locks (documented risk),
  nothing throws.

### 6.4 messaging (L3)
- `EventPublisher` over Kafka: idempotent producer, `EventEnvelope` JSON, trace propagation, topic names from
  config, warm-up option.
- Outbox: `OutboxStore` port (JDBC adapter), used automatically when Kafka is unavailable or when the caller
  wants transactional publishing; relay job with backoff.
- Consumer base: retry topics, DLT, replay endpoint, error handler, consumer metrics, trace continuation.
- `AuditSink` implementation (publishes `AuditEvent`).

### 6.5 resilience (L3)
- Named policies (`amef.resilience.policies.<name>`: timeout, retry with backoff, circuit breaker, bulkhead, rate
  limiter); servlet decorators and Reactor operators; default policies `external-default` and `critical`;
  metrics and health.

### 6.6 external-call (L4)
- `ExternalCallPort` with one request/response model for REST, SOAP and MQ (JMS).
- Client registry by system name; configuration-driven definitions (endpoint providers, templates, flows)
  loaded through a `DefinitionRepository` port (JDBC adapter, YAML adapter) and cached through the redis brick.
- Template-driven requests (Velocity) and rule/condition evaluation (MVEL), response mapping, validation, multi-step
  flows (sequence, composite, query, add-params tasks).
- Every call: resilience policy by name, masking, an `AuditEvent` through messaging, metrics.
- Optional `PayloadCodec` plug-in for encrypted payloads; keys only from configuration/secret stores.
- MQ is blocking: in the reactive variant it runs on a bounded elastic scheduler.

### 6.7 cache-sync (L4, for back-office services)
- Keeps distributed caches consistent with the primary DB when a back office writes whitelisted tables.
- Whitelist in config: entity/table, key expression, mode, cache region.
- Interception: `@SyncCache` AOP on service-layer writes (both stacks) and a Hibernate post-commit entity
  listener (servlet/JPA). Reactive (R2DBC) uses the AOP path only (documented).
- Only after commit. Modes: `EVICT`, `WRITE_THROUGH`, `VERSION_BUMP`. Publishes on the invalidation bus so every
  pod drops L1. Failures go to the outbox and are retried; TTLs are the last safety net.
- Admin API: re-sync a table or key range (for changes made outside the application, e.g. SQL scripts), list
  keys, inspect values. Config-driven full/incremental table→Redis sync.

## 7. Apps

### 7.1 gateway (reactive)
- Spring Cloud Gateway (WebFlux). Routes, filters and policies stored in Postgres, served from Redis through the
  redis brick, last-known-good table kept in memory, refresh endpoint.
- Per-route policies: rate limit (redis brick), XSS and SQL-injection screening, response cache (redis brick),
  each with an optional JEXL condition; screening runs before rate limiting.
- Auth via `TokenValidator` port: session-bound JWT (keys from config/JWKS) or stateless OAuth2 resource server;
  per-route public/private flag; configurable token capture from a login response (JSONPath).
- `AccessRule` chain: IP block (default), device/user block (data synced by cache-sync), geo-block plug-in with a
  `GeoResolver` port (no default third-party call).
- `PayloadCodec` port (no-op default). Never logs decrypted bodies.
- Request logs → `AuditSink`; field extraction by configurable JSONPath map.
- Circuit breaker and fallback via resilience brick; CORS/SameSite handling from config; OpenAPI aggregation
  list from config.
- Optional tenant-affinity routing plug-in (route a tenant to a pod group), off by default.

### 7.2 audit-service
Consumes `AuditEvent` with the messaging consumer base, flattens payloads, persists through ports (Postgres
adapter; second sink optional), exposes a query API by traceId/subjectId/time range.

### 7.3 sample services (reactive and servlet)
Same API, fictional Acme domain. Shows: ports/adapters, cached reader decorator, external call to WireMock with a
resilience policy, events and audit, a back-office write synced by cache-sync, error envelope, guard passing,
unit + integration tests, QA suite coverage.

## 8. QA automation (`qa/`)

Rest Assured + TestNG + AssertJ + Allure, Gatling for load. Layering: Test → Client → SpecFactory. Clients hold
no assertions. JSON-driven data providers, JSON-schema contract checks, retry listener, environments `local` and
`docker`, suites `smoke` and `regression`, one generic runner script. Runs against both sample services and the
gateway admin API.

**Rule:** every feature added to any app (by a human or by the `add-feature` pipeline) must add its QA artefacts:
client method, request/response records, positive and negative tests, test data, schema, suite entry, and a
Gatling scenario when the feature is on a hot path.

## 9. AI layer

### 9.1 Design (carried over from a proven personal setup)
1. **Building blocks → skills.** Small Markdown notes in `ai/blocks/`, each one rule or procedure written as a
   direct instruction at the step where it applies. Skill sources in `ai/skills/` include notes with
   `{{include blocks/X.md}}` or reference them by path when only one step needs them. `tools/build_skills.py`
   compiles sources into `.claude/skills/<name>/SKILL.md` (and optionally Cursor commands), installs, and removes
   retired skills. Small skills, low tokens.
2. **The LLM decides, code enforces.** Anything that must always hold is a Python tool or a test: scaffolding,
   manifest validation, guard rules, forbidden-terms and secret scans, report generation. The AI writes values and
   business code; tools do the rest.
3. **Rules are data.** Manifests (`brick.yaml`), naming, error-code registry, policies are files the tools and
   skills read.
4. **Explicit invocation.** Skills are invoked by name (`disable-model-invocation: true`), print short output.
5. **Self-maintenance.** An `edit-skills` skill knows where every rule lives: change → build → validate → commit.

### 9.2 Skills
| Skill | Does |
|---|---|
| `add-feature` | Pipeline: clarify → design ports/use case → code (both stacks if the target is a brick) → unit tests → QA artefacts (§8) → docs/manifest update → `/review` → fix → report |
| `new-brick` | Scaffolds a brick (core/reactive/servlet, auto-config, properties, behaviour suite, README, `brick.yaml`) using `amef new brick` |
| `compose-service` | From a plain-English description: choose stack + bricks (via manifests), run `amef new service`, write ports/adapters/use cases, tests, QA suite entries |
| `fix-guard` | Explains architecture-guard/coverage failures and fixes them |
| `review` | Runs the review pipeline (§9.3) and writes a report |
| `new-pipeline` | Creates a new multi-step skill/pipeline from building blocks (the pipeline that builds pipelines) |
| `edit-skills` | Changes a rule or skill in the right place, rebuilds, validates |
| `explain` | Answers "how does X work" from brick READMEs, manifests and ADRs |

### 9.3 Review pipeline (agents)
Subagents in `.claude/agents/`: **security-reviewer** (secrets, injection, authn/authz gaps, PII in logs, unsafe
deserialisation, dependency risk), **performance-reviewer** (blocking on event loop, N+1, missing timeouts, unbounded
caches/queues, cache stampede, connection pools), **architecture-reviewer** (single-owner rule, ports, layering,
brick reuse instead of duplication), **test-reviewer** (missing cases, weak assertions, both stacks covered, QA
artefacts present). `/review` runs them in parallel over a diff or a module and merges findings into one prioritised
report (`docs/reports/reviews/`). The same reviewers run on pull requests via the Claude Code GitHub Action.

### 9.4 Tools (`tools/`, Python 3.11+)
`amef` CLI (Typer): `doctor`, `new service`, `new brick`, `add <brick>`, `up` (compose profiles from manifest
`infra`), `graph`, `catalog`, `demo`; `build_skills.py`; `guard/forbidden_terms.py`, `guard/install-hooks.py`;
`manifests.py` (validate/generate); `evals/run.py`.

### 9.5 Evals
`ai/evals/*.yaml`: prompts such as "compose a reactive service with cached reads and back-office sync". The runner
executes them through Claude Code headless mode in CI (manual/nightly trigger, needs an API key secret) and checks
that the result compiles, passes the guard and tests. Results summarised in the README.

## 10. Docker and demo
Compose profiles per infra (redis, kafka in KRaft mode, postgres, wiremock, kafka-ui, observability = Grafana +
Tempo + Loki + Prometheus). `amef demo` starts gateway → sample service → WireMock external call → Kafka →
audit-service, then prints the Grafana link where one trace spans all of them with `userId` as baggage. Images for
gateway, audit-service and sample services. A devcontainer for GitHub Codespaces (Java, Maven, Docker, Python,
Claude Code).

## 11. Documentation and presentation
- Root README: one-line pitch, badges, Mermaid architecture diagram, brick catalogue (generated), 5-minute quick
  start, demo screenshot/GIF, "how the AI layer works", link to the knowledge-engine project for project memory.
- Brick README layout: What it does → When to use → Quick start (reactive, servlet) → Configuration (generated table)
  → Uses / used by → Design notes → Limitations.
- `docs/adr/` for decisions, `docs/guides/` for how-tos, MkDocs Material site on GitHub Pages (M11).
- `CONTRIBUTING.md`, `CHANGELOG.md`, Apache-2.0 `LICENSE`, `SECURITY.md`, issue/PR templates, Dependabot.

## 12. Quality gates (every milestone, every PR)
`mvn clean verify` green with Testcontainers ITs actually run; architecture guard green; JaCoCo gate; gitleaks;
forbidden-terms check (local); manifests valid; generated docs up to date; `/review` report with no unresolved
high-severity findings.
