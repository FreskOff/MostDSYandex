# Security

MostDSYandex runs locally. It does not need a Yandex token and it does not talk to a custom backend.

## Supported versions

Use the latest code on `main`.

## Reporting a problem

If you find something risky, open a private report or contact the maintainer. Include:

- the version or commit;
- how to reproduce it;
- what you think the impact is;
- logs if they help, with secrets removed.

## Secrets

- Do not commit `.env`.
- Do not share Discord application secrets.
- `DISCORD_CLIENT_ID` is public enough for this use case. Client secrets are not.
