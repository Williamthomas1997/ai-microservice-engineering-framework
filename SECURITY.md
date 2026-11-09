# Security policy

## Supported versions

The project has no release yet. Security fixes go to `main` until the first release; after that, the latest minor
version is supported.

## Reporting a vulnerability

Please do **not** open a public issue. Use GitHub private vulnerability reporting ("Security" tab, then
"Report a vulnerability") on this repository. Include the affected module, version or commit, reproduction steps
and impact. You will get an answer within 7 days.

## What the project does to stay safe

- No secrets in the repository: configuration uses `${ENV}` placeholders, gitleaks runs locally (git hooks) and in CI.
- Dependencies are pinned in one BOM and updated through Dependabot.
- Review agents check every change for secrets, injection, authn/authz gaps, PII in logs and unsafe deserialisation.
