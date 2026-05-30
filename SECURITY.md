# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Instead, report them privately through GitHub's private vulnerability reporting:

1. Go to the [Security tab](https://github.com/pwiereng/inxr2/security/advisories/new).
2. Click **Report a vulnerability**.
3. Describe the issue, including steps to reproduce and any affected versions.

You can expect an initial response within a few days. Once the issue is
confirmed and fixed, the advisory will be published and credit given to the
reporter (unless anonymity is requested).

## Supported versions

INXR2 is under active development; security fixes are applied to the `main`
branch. There are no separately maintained release branches at this time.

## Scope

INXR2 is designed to be self-hosted and run locally or within a trusted
environment. When deploying:

- Always set a strong `POSTGRES_PASSWORD` and `SECRET_KEY` in `.env.prod`
  (never use the development defaults from `.env.dev` in production).
- Do not expose the backend or database directly to untrusted networks
  without authentication in front of it.
- Index only repositories you trust.
