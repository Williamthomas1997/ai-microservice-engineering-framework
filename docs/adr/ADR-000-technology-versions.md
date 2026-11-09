# ADR-000: Technology versions

- Status: accepted (M0, 2026-11-09)
- Applies to: `bom/pom.xml`, `build-parent/pom.xml`, `.mvn/wrapper/maven-wrapper.properties`, CI

## Context

Spec 4 asks for Java 21, the latest GA Spring Boot, and the Spring Cloud release train that officially supports it
and ships Spring Cloud Gateway Server WebFlux. If the newest Boot has no compatible Gateway release, use the newest
Boot that does. All other libraries are pinned once, in the BOM.

## Decision

### Platform

| Item | Version | Why |
|---|---|---|
| Java | 21 (`maven.compiler.release=21`) | LTS baseline required by the spec. Builds verified on JDK 21.0.11. |
| Spring Boot | **4.1.2** | Latest GA (spring.io marks 4.1.2 as current; 4.2.0 is RC2 only). |
| Spring Cloud | **2025.1.4** | Latest GA train. Officially supports Boot 4.1.x "starting with 2025.1.2" (spring.io compatibility table); its compatibility verifier accepts `4.0.x` and `4.1.x`. The next train, 2026.0, targets Boot 4.2 and is RC2 only. |
| Spring Cloud Gateway Server WebFlux | 5.0.4 (from the train) | `spring-cloud-starter-gateway-server-webflux` |
| Spring Framework | 7.0.10 (Boot-managed) | |
| Jackson | **3.1.7** (`tools.jackson.*`, Boot default) + 2.21.x annotations | Boot 4 uses Jackson 3. Copied code must use Jackson 3 APIs (`tools.jackson.databind.ObjectMapper`/`JsonMapper`). Jackson 2 (`jackson-2-bom` 2.21.7, Boot-managed) only where a library forces it. |
| Maven (wrapper) | 3.9.16, wrapper 3.3.4 (`only-script`, SHA-256 pinned) | Latest 3.9.x; matches the 3.9 line installed locally. Maven 3.10.0 / 4.0 RCs not adopted yet. |

### Libraries (Boot-managed unless stated)

| Library | Version | Notes |
|---|---|---|
| Micrometer / Micrometer Tracing | 1.17.2 / 1.7.2 | OTel bridge via `spring-boot-starter-opentelemetry` (Boot 4 module layout). |
| OpenTelemetry | 1.62.0 | |
| Testcontainers | 2.0.5 | 2.x artifact names: `testcontainers-junit-jupiter`, `testcontainers-postgresql`, `testcontainers-kafka`. Works with Docker Engine 29 (API 1.54). |
| Caffeine | 3.2.4 | |
| Lettuce / Spring Kafka / Kafka | 7.5.2 / 4.1.2 / 4.2.2 | Used by the redis and messaging bricks. |
| JUnit Jupiter / AssertJ | 6.0.3 / 3.27.7 | |
| Resilience4j | **2.4.0** (pinned, BOM import) | `resilience4j-spring-boot4` exists only from 2.4.0. Spring Cloud 2025.1.4 manages 2.3.0 through its circuit-breaker BOM, which mixed versions in the first trial (`resilience4j-spring6` resolved to 2.3.0). Fix: `resilience4j-bom` is imported **before** Spring Cloud in `amef-bom`, so 2.4.0 wins for every Resilience4j artifact. Compatibility of Spring Cloud CircuitBreaker with 2.4.0 is re-checked when the gateway uses it (M7). |
| ArchUnit | 1.5.1 (pinned) | `archunit-junit5`. |
| WireMock | 3.13.2 (pinned) | `wiremock-standalone` (shaded, so its Jackson 2 / Jetty do not clash with Boot 4). 4.0 is still beta. |
| BlockHound | 1.0.18.RELEASE (pinned) | Needs `-XX:+AllowRedefinitionToAddDeleteMethods` on JDK 13+; reactive modules add it. |
| Apache Velocity | 2.4.1 (pinned) | `velocity-engine-core`. |
| MVEL | 2.6.0.Final (pinned) | `mvel2`. |
| Apache Commons JEXL | 3.7.1 (pinned) | `commons-jexl3`. |
| Rest Assured | 6.3.0 (pinned) | Not managed by Boot 4.1. Also `json-schema-validator`. |
| TestNG | 7.12.0 (pinned) | |
| Allure | 3.1.1 (pinned, `allure-bom` import) | `allure-testng`, `allure-rest-assured`. |
| Gatling | 3.16.0 (pinned) + `gatling-maven-plugin` 4.21.12 | Java DSL. |
| JaCoCo plugin | 0.8.16 | Not managed by Boot. |
| Build plugins | Boot 4.1.2 versions (compiler 3.15.0, Surefire/Failsafe 3.5.6, Enforcer 3.6.3, ...) | Copied into `amef-build-parent` properties because imported BOMs do not carry plugin versions. |
| jMolecules | 2025.0.2 BOM (2.0.1 hexagonal annotations) | **Evaluated only, not adopted.** Compiles with the stack. Decision (own `@Port`/`@Adapter`/`@UseCase` vs jMolecules) is ADR-004 in M1. Not in the BOM. |

## Verification

1. Versions were read from Maven Central metadata and the Spring project API on 2026-11-09 (latest GA, excluding
   milestones/RCs), and the Boot/Cloud compatibility from the spring.io Spring Cloud page and the
   `CompatibilityVerifierProperties` defaults inside `spring-cloud-commons` 5.0.4.
2. Throwaway project A (Boot 4.1.2 parent + Spring Cloud 2025.1.4, deleted afterwards): one `@SpringBootTest`
   started a Spring Cloud Gateway Server WebFlux app with a route to a WireMock server and got the proxied JSON back
   through `WebTestClient`; the same context exposed a Resilience4j `CircuitBreakerRegistry`
   (`resilience4j-spring-boot4`), a Micrometer `Tracer` (OTel bridge) and a Jackson 3 `ObjectMapper`. Further tests
   evaluated MVEL, JEXL and Velocity expressions, a Caffeine cache, an ArchUnit rule, BlockHound (detected a
   `Thread.sleep` on a parallel scheduler) and Testcontainers (started `redis:7-alpine`). Result: 4 tests, 0
   failures.
3. Throwaway project B (plain Java 21): TestNG 7.12 + Rest Assured 6.3 + Allure 3.1.1 filter called WireMock and
   asserted the body; a Gatling 3.16 Java-DSL simulation compiled. Result: 1 test, 0 failures.
4. The real skeleton builds with `./mvnw clean verify`, including the Testcontainers smoke IT in `platform/rules`.

Observed while verifying (input for later milestones):
- With `spring-boot-starter-opentelemetry` on the classpath, Boot 4.1 exports OTLP metrics to `localhost:4318` by
  default and logs a connection error when no collector runs. The observability brick (M2) must default export to
  off unless an endpoint is configured.
- Boot 4 test starters are per-technology (`spring-boot-starter-webflux-test`, `...-webmvc-test`, ...);
  `@AutoConfigureWebTestClient` moved to `org.springframework.boot.webtestclient.autoconfigure`.

## Consequences

- Change versions only in `bom/pom.xml` (libraries) or `build-parent/pom.xml` (plugins), together with this ADR.
- Dependabot proposes updates; Boot/Cloud minor upgrades need the compatibility check above (Cloud train first).
- Move to Boot 4.2 when Spring Cloud 2026.0 is GA and a gateway release supports it.
