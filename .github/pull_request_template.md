## What and why

## Checklist

- [ ] `./mvnw clean verify` passes locally (Docker running, integration tests ran)
- [ ] `python tools/manifests.py validate` and `python tools/manifests.py generate --check` pass
- [ ] Brick changes cover **both** stacks and the shared behaviour suite
- [ ] No second Redis/Kafka/HTTP-client/tracing setup (single-owner rule)
- [ ] No secrets, organisation names or real hosts; config uses `${ENV}` placeholders
- [ ] App features add their `qa/` artefacts
- [ ] README / brick README / `brick.yaml` / ADRs / CHANGELOG updated
- [ ] `/review` run, high findings fixed or justified below

## Review notes
