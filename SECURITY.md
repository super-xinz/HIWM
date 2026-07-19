# Security policy

## Supported version

Security fixes currently target the latest `main` branch and the `0.1.x` line.

## Reporting a vulnerability

Use GitHub private vulnerability reporting for the repository when available. If it is not enabled, contact the repository owner privately before opening a public issue. Do not include credentials, real conversation data, face or voice recordings, provider responses, or a working exploit in a public report.

Include the affected revision, environment, reproduction conditions, expected impact, and the smallest safe proof of concept. Reports involving credential exposure, consent bypass, cross-session data access, ledger integrity, arbitrary code execution, or unsafe high-impact inference should be treated as high priority.

## Secrets and user data

- Keep provider keys either in the ignored project-root `.env` or in the local
  service's process memory through the setup screen; `.env.example` must
  contain placeholders only.
- Runtime credential replacement and explicit RTC teardown are loopback-only
  by default. A non-loopback deployment must set `HIWM_RUNTIME_CONTROL_TOKEN`
  and send the same value as a Bearer token.
- Do not commit `temp/`, `logs/`, browser exports, model responses, raw media, or screenshots containing personal data.
- Revoke exposed provider keys immediately and remove them from all reachable Git history before publishing.
- Test with synthetic or explicitly consented data and document retention behavior.
