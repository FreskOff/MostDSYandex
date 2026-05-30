# Security Policy

MostDSYandex is a local desktop bridge. It does not require a Yandex token and does not send secrets to a backend service.

## Supported versions

Only the latest version on the main branch is supported.

## Reporting a vulnerability

Open a private report or contact the maintainer directly. Please include:

- affected version or commit;
- steps to reproduce;
- expected impact;
- relevant logs with secrets removed.

## Secret handling

- Do not commit `.env`.
- Do not share Discord application secrets.
- `DISCORD_CLIENT_ID` is not a secret, but application credentials are.
