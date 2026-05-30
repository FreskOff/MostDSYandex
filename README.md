# MostDSYandex

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-10%2F11-0078D4?logo=windows&logoColor=white)
![Discord](https://img.shields.io/badge/Discord-Rich%20Presence-5865F2?logo=discord&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

Yandex Music status for Discord, without the sad question-mark cover.

[![Download for Windows](https://img.shields.io/badge/Download-Windows%20EXE-2ea44f?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/FreskOff/MostDSYandex/releases/latest/download/MostDSYandex.exe)

This is a small Windows bridge. It watches the track that Yandex Music exposes through Windows media controls, finds the same track on Yandex Music, grabs the cover and links, then sends a Discord Rich Presence card.

It is built for the desktop app, but browser playback can work too if Windows sees it as a media session.

## What it does

- Shows the current Yandex Music track in Discord.
- Uses the real cover when Yandex Music returns a good match.
- Adds `Listen` and `Album` buttons.
- Keeps Discord's timer stable instead of restarting it every poll.
- Writes a local `history.csv` if you want to see what played.
- Starts with Windows if you install the Startup shortcut.
- Has `--once` for a quick check and `--doctor` when something feels off.
- Does not need a Yandex token.

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
- Yandex Music desktop app, or browser playback that appears in Windows media controls

## Download

The easiest install is the release exe:

[Download `MostDSYandex.exe`](https://github.com/FreskOff/MostDSYandex/releases/latest/download/MostDSYandex.exe)

Put it in its own folder, run it, and keep Discord open. If you want config, place a `.env` file next to the exe.

If you want the source version instead, use the install steps below.

## Install

```powershell
git clone https://github.com/FreskOff/MostDSYandex.git
cd MostDSYandex

python -m pip install -r requirements.txt
copy .env.example .env

python presence.py --doctor
python presence.py
```

If you do not care about the terminal, double-click `run.bat`.

## Useful commands

Check what the script sees, then quit:

```powershell
python presence.py --once
```

Run the health check:

```powershell
python presence.py --doctor
```

Start the bridge:

```powershell
python presence.py
```

Stop background copies:

```powershell
.\stop.bat
```

## Autostart

Install the Windows Startup shortcut:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\install_autostart.ps1
```

Remove it:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\uninstall_autostart.ps1
```

The Startup script checks whether `presence.py` is already running before it starts a new copy.

## Config

Copy `.env.example` to `.env` and tweak it there.

| Variable | Default | What it changes |
| --- | --- | --- |
| `DISCORD_CLIENT_ID` | `1504152588684230656` | Discord app id. |
| `POLL_SECONDS` | `15` | How often the script checks Windows media controls. Values below 15 are ignored. |
| `LISTEN_BUTTON_LABEL` | `Listen` | Text on the track button. |
| `ALBUM_BUTTON_LABEL` | `Album` | Text on the album button. |
| `DISCORD_SMALL_TEXT` | `Playing from Yandex Music` | Hover text for the small image. |
| `DISCORD_SMALL_IMAGE` | `f` | Small image asset key from the Discord Developer Portal. |
| `DISCORD_FALLBACK_LARGE_IMAGE` | empty | Large image asset key to use when no cover is available. |
| `PAUSE_BEHAVIOR` | `show` | `show` marks the card as paused. `clear` removes it. |
| `MIN_MATCH_SCORE` | `70` | Minimum match score before the script trusts a Yandex result. |
| `HISTORY_ENABLED` | `1` | Set to `0` to stop writing `history.csv`. |

## A couple of Discord quirks

- Discord may hide Rich Presence buttons from you on your own card. Other people can still see them.
- The top line comes from the Discord application name. Rename the app in the Developer Portal if you want it to say `Yandex Music`.
- Keep the poll interval at 15 seconds or higher. The script only sends a Discord update when the visible status changes.

## Files

```text
presence.py              main script
run.bat                  start it by hand
stop.bat                 stop running copies
start_presence.ps1       hidden launcher used by autostart
requirements.txt         Python dependencies
.env.example             config template
scripts/                 build and autostart helpers
.github/                 release workflow and issue templates
```

## Build the exe

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1
```

The exe lands in `dist\MostDSYandex.exe`. Release builds are made by GitHub Actions when a `v*` tag is pushed.

## License

MIT. See [LICENSE](LICENSE).
