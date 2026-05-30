# Contributing

Thanks for wanting to improve MostDSYandex.

## Local setup

```powershell
python -m pip install -r requirements.txt
copy .env.example .env
python presence.py --doctor
```

## Development notes

- Keep the Discord poll interval at 15 seconds or higher.
- Send Discord activity updates only when the visible state changes.
- Do not commit `.env`, logs, or `history.csv`.
- Keep Windows support first-class; this project depends on Windows media sessions.

## Pull requests

Please include:

- what changed;
- how you tested it;
- screenshots if the Discord card changed.
