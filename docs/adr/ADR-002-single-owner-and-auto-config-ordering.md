# ADR-002: Single-owner rule and auto-configuration ordering

- Status: accepted (M0, 2026-11-09)

## Context

Spec 2.2: exactly one brick creates each infrastructure bean. Reference implementations each created their own
Redis connections, Kafka producers, HTTP clients and tracing setup, which led to duplicated pools, inconsistent
timeouts and lost trace context. Spec 2.5 requires replaceable beans and explicit ordering.

## Decision

### Ownership

| Concern | Owner | Owns (examples) |
|---|---|---|
| MDC, tracing, baggage, log format, masking | observability | `ObservationRegistry` customisers, request-context filters, context-propagating task decorators |
| Redis connections, templates, scripts | redis | connection factory customisation, templates, `CachePort`/`LockPort`/`IdempotencyPort` adapters |
| Kafka producers/consumers, outbox | messaging | producer/consumer factories, `EventPublisher`, `AuditSink` |
| Resilience4j registries | resilience | circuit breaker / retry / bulkhead / rate limiter / time limiter registries and named policies |
| Outbound HTTP/SOAP/MQ clients | external-call | client registry, `ExternalCallPort` |

Nobody else (other bricks, apps, sample services, the gateway) creates these beans. Gateway caching, rate limiting,
logging and audit go through the bricks.

### Enforcement

1. **Consumers:** `amef-build-parent` runs Maven Enforcer `bannedDependencies` (direct dependencies only) with the
   union of the `bans` lists of all `brick.yaml` files. `tools/manifests.py validate` fails if the two lists differ.
   The platform's apps re-enable this rule (platform-parent switches it off only for the bricks that own the
   libraries).
2. **Platform:** the architecture-reviewer agent and (from M1) ArchUnit rules flag bean definitions of owned types
   outside the owner brick.
3. **Review:** `/review` checks every diff for duplicated infrastructure.

### Auto-configuration ordering

- Each brick has one `@AutoConfiguration` per stack, listed in `AutoConfiguration.imports`.
- Ordering is declared by name with `@AutoConfiguration(after = ..., before = ...)`, following the layers:
  observability after Boot's observation/tracing auto-configs; redis/messaging/resilience `after` observability
  (and after Boot's Redis/Kafka auto-configs they customise); external-call and cache-sync `after` the L3 bricks
  they use; apps never declare auto-configuration ordering against bricks. No numeric `@AutoConfigureOrder`.
- Every brick bean is `@ConditionalOnMissingBean` (by type, or by name for shared types) so a service can replace
  it; replacing a bean never requires excluding an auto-configuration.
- Each brick has `amef.<brick>.enabled` (default `true`). Disabled = documented fail-safe behaviour (spec 2.7), never
  an exception at startup.
- Every auto-configuration gets a context test (`ApplicationContextRunner` / `ReactiveWebApplicationContextRunner` /
  `WebApplicationContextRunner`) proving: beans present by default, backing off for a user bean, off when disabled.

## Consequences

- Services cannot pull `spring-kafka`, `spring-boot-starter-data-redis`, `resilience4j-spring-boot4` etc. directly;
  the error message points to the brick catalogue.
- Bricks may still bring those libraries transitively (the ban checks direct dependencies only).
- Adding a new owned concern = add it to a brick's `bans` and the build-parent list in the same commit.
