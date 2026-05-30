# MostDSYandex

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-10%2F11-0078D4?style=for-the-badge&logo=windows&logoColor=white)
![Discord](https://img.shields.io/badge/Discord-Rich%20Presence-5865F2?style=for-the-badge&logo=discord&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

Yandex Music to Discord Rich Presence bridge for Windows.

MostDSYandex reads the currently playing Yandex Music track from Windows media sessions, finds the matching track on Yandex Music, pulls the cover art, and publishes a clean Discord activity card with progress, cover, and buttons.

## Features

- Real current-track detection from Windows media sessions.
- Discord Rich Presence with track title, artist, cover, timer, and album hover text.
- `Listen` and `Album` buttons that open Yandex Music.
- Smart match scoring to avoid wrong covers and links.
- Updates Discord only when the visible state changes, so the timer does not reset every poll.
- Optional pause handling: keep the card or clear it.
- Startup shortcut autostart for Windows.
- `--once` and `--doctor` diagnostics.
- Local listening history in `history.csv`.
- No Yandex token required.

## Preview

```text
Listening to Yandex Music

VOID (Slowed)
RPA, LIFT TUBE, MNDCTRL
VOID

[ Listen ] [ Album ]
```

## Requirements

- Windows 10 or 11
- Python 3.12+
- Discord desktop app
- Yandex Music desktop app or browser playback visible to Windows media controls

## Quick Start

```powershell
git clone https://github.com/your-name/MostDSYandex.git
cd MostDSYandex

python -m pip install -r requirements.txt
copy .env.example .env

python presence.py --doctor
python presence.py
```

Or double-click `run.bat`.

## Commands

```powershell
python presence.py --once
```

Print the detected track, cover, Yandex URL, and match score once.

```powershell
python presence.py --doctor
```

Check Python, autostart, duplicate processes, media detection, cover lookup, Yandex links, and Discord RPC.

```powershell
python presence.py
```

Run the bridge.

## Autostart

Install autostart:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\install_autostart.ps1
```

Remove autostart:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\uninstall_autostart.ps1
```

The autostart shortcut launches `start_presence.ps1`, which skips launch when `presence.py` is already running.

## Configuration

Copy `.env.example` to `.env` and edit values as needed.

| Variable | Default | Description |
| --- | --- | --- |
| `DISCORD_CLIENT_ID` | `1504152588684230656` | Discord application id. |
| `POLL_SECONDS` | `15` | Media-session poll interval. Minimum effective value is 15 seconds. |
| `LISTEN_BUTTON_LABEL` | `Listen` | Track button label. |
| `ALBUM_BUTTON_LABEL` | `Album` | Album button label. |
| `DISCORD_SMALL_TEXT` | `Playing from Yandex Music` | Small icon hover text. |
| `DISCORD_SMALL_IMAGE` | `f` | Discord Developer Portal asset key for small image. |
| `DISCORD_FALLBACK_LARGE_IMAGE` | empty | Fallback large asset key when cover URL is missing. |
| `PAUSE_BEHAVIOR` | `show` | `show` keeps the card; `clear` removes it on pause. |
| `MIN_MATCH_SCORE` | `70` | Minimum score required before showing cover/buttons. |
| `HISTORY_ENABLED` | `1` | Set to `0` to disable `history.csv`. |

## Notes

- Discord may not show Rich Presence buttons to the account that owns the activity, but other users can see them.
- The Discord application name controls the top line, for example `Listening to Yandex Music`.
- Keep `POLL_SECONDS` at 15 seconds or higher.
- `history.csv`, logs, and `.env` are ignored by git.

## Project Layout

```text
presence.py              Main bridge
run.bat                  Manual launcher
stop.bat                 Stops running bridge processes
start_presence.ps1       Hidden background launcher
install_autostart.ps1    Creates Startup shortcut
uninstall_autostart.ps1  Removes Startup shortcut
requirements.txt         Runtime dependencies
.env.example             Configuration template
```

## License

MIT. See [LICENSE](LICENSE).
