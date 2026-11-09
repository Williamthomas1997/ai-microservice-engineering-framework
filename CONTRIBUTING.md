# Contributing

Thanks for your interest. The project is under construction (see the status in the [README](README.md)); issues
and discussions are welcome, larger pull requests are best discussed in an issue first.

## Before you start

- Read [`docs/MASTER_SPEC.md`](docs/MASTER_SPEC.md) (requirements),
  [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) and the [ADRs](docs/adr/).
- Requirements: JDK 21, Docker (Testcontainers), Python 3.11+.

## Development loop

```bash
./mvnw clean verify                          # full build incl. integration tests (Docker must run)
pip install -r tools/requirements.txt
python tools/manifests.py validate           # manifests, layering, POM dependencies, enforcer bans
python tools/manifests.py generate           # refresh the README catalogue and docs/architecture.md
python -m pytest tools -q
python tools/guard/install_hooks.py          # once per clone: pre-commit, commit-msg, pre-push guards
```

## Rules for changes

- **Generic only.** No organisation names, hosts, keys, table names or business rules. Samples use the fictional
  company Acme.
- **Single owner per concern.** Never create a second Redis/Kafka/HTTP-client/tracing setup; use the owning brick
  ([ADR-002](docs/adr/ADR-002-single-owner-and-auto-config-ordering.md)).
- **Both stacks.** Every brick change covers `reactive` and `servlet` and the shared behaviour suite.
- **Layers point down.** A module never depends on a higher layer; the build fails if it does.
- **Tests for real.** Testcontainers / WireMock for integration tests; no mocked core behaviour.
- **QA artefacts.** Every app feature adds its `qa/` client, tests, data and schema (spec 8).
- **No secrets.** Configuration uses `${ENV}` placeholders; `.env.example` has placeholders only.
- Update the brick README, `brick.yaml`, generated docs and ADRs in the same change.

## Pull requests

- Keep them focused; describe what and why; link the issue.
- CI must be green (build, integration tests, manifests, gitleaks).
- If you use Claude Code, run the `/review` command and address high findings.
- Add an entry under `Unreleased` in [`CHANGELOG.md`](CHANGELOG.md).

By contributing you agree that your contributions are licensed under the Apache License 2.0.
