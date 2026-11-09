# ADR-001: Module layout and two-stack strategy

- Status: accepted (M0, 2026-11-09)

## Context

Spec 3 fixes the top-level layout (`bom`, `build-parent`, `foundation`, `bricks`, `apps`, `qa`, `ai`, `tools`,
`docker`, `docs`) and spec 2.4 requires every brick to work on WebFlux and on Spring MVC with one behaviour. We
also need an internal parent for the platform's own modules and a place for checks that span all modules.

## Decision

1. **Brick = three Maven modules**: `bricks/<brick>/core` (stack-neutral logic, properties, ports' implementations
   that do not touch the web stack), `.../reactive` (WebFlux/Reactor adapters and auto-config) and `.../servlet`
   (Spring MVC/blocking adapters and auto-config). Artifacts `amef-<brick>-{core,reactive,servlet}`, packages
   `io.github.williamthomas1997.amef.<brick>.{core,reactive,servlet}`. Stack modules depend on their `core`; `core`
   never depends on a web stack.
2. **One behaviour, two stacks:** each brick's `core` publishes a **test-jar** with abstract behaviour tests
   (`*BehaviourTest`); `reactive` and `servlet` extend them with their wiring. A brick change is done only when
   both stacks pass the suite (reactive first, then servlet). Reactive tests run with BlockHound.
3. **No brick aggregator POMs:** the root reactor lists leaf modules directly (`bricks/redis/core`, ...). The
   brick folder holds `brick.yaml` and `README.md`. This keeps one place (the root) to see the build order.
4. **POM hierarchy:** `amef-bom` (versions) ← `amef-build-parent` (consumers' parent with gates) ←
   `amef-platform-parent` (internal, in `platform/parent`) ← all platform modules. The platform builds with the
   same plugins and gates it gives to consumers ("dogfooding"); only the banned-dependency rule is switched off,
   because bricks own those libraries. `amef-root` is an aggregator without inheritance. Parents are resolved by
   `relativePath`, so a clean checkout builds without installing anything first.
5. **`platform/` folder** for build-internal modules that the spec does not name: `platform/parent` and
   `platform/rules` (test-only module that depends on every platform module and runs the layer rule and the
   Testcontainers smoke IT). Not published.
6. **Manifests for non-bricks:** foundation modules, apps and `qa` get a `module.yaml` with the same schema as
   `brick.yaml` (no `stacks`). This lets tools validate `requires` across all layers and lets the layer rule read
   every module's layer and package from data, not code.
7. **`qa/`** is a standalone Maven project (parent `amef-build-parent` via `relativePath`, not in the reactor).
8. **Apps** are plain JAR modules until their milestone; when they become Boot applications, the repackaged jar uses
   a classifier so the main artifact stays a normal library for `platform/rules`.

## Consequences

- 25 module stubs + 3 POM-only modules + `platform/rules` in the reactor; each stub has a `package-info.java`.
- Adding a brick = folder with three modules + `brick.yaml` + `README.md` + root `<module>` entries + BOM entries;
  `tools/manifests.py validate` reports anything missing. M10's `amef new brick` automates it.
- Alternatives rejected: one module per brick with optional web dependencies (classpath ambiguity, blocking code
  leaking into reactive apps); separate repos per brick (no shared behaviour suite, version drift).
