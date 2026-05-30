# Contributing

This project is tiny on purpose. Changes are welcome, but keep the bridge boring and reliable.

## Setup

```powershell
python -m pip install -r requirements.txt
copy .env.example .env
python presence.py --doctor
```

## Before opening a PR

- Keep the poll interval at 15 seconds or higher.
- Do not send Discord updates on every poll. Update only when the card changes.
- Do not commit `.env`, logs, or `history.csv`.
- Test on Windows. The media-session part is Windows-specific.
- Add a screenshot if you changed what the Discord card looks like.

## PR notes

Tell me what changed and how you checked it. Short is fine.
