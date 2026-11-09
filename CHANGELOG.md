# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project will use
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) from its first release.

## [Unreleased]

### Added

- M0: repository skeleton with every planned module as a stub (foundation, six bricks with core/reactive/servlet,
  four apps, standalone `qa`), `amef-bom` (Spring Boot 4.1.2, Spring Cloud 2025.1.4 and pinned libraries),
  `amef-build-parent` (enforcer bans, Surefire/Failsafe, JaCoCo gate), Maven wrapper.
- Module manifests (`brick.yaml`, `module.yaml`) and `tools/manifests.py` (validate, generate) with tests.
- Layer rule (ArchUnit) and Testcontainers smoke test in `platform/rules`.
- Local guards: forbidden-terms check and gitleaks through git hooks and a Claude Code hook.
- CI workflow (build, integration tests, manifests, gitleaks) and Dependabot.
- Early review agents and the `/review` command.
- Implementation plan, architecture page, ADR-000 to ADR-003, project documents.
