# Changelog

## 0.2.0 - 2026-05-31

- Adds a Windows tray app mode for the exe.
- Starts release builds without a console window.
- Adds a generated project icon/avatar.
- Adds a small status window and doctor window from the tray menu.

## 0.1.1 - 2026-05-31

- Adds field links for newer Discord clients.
- Links the song title and cover to the Yandex Music track.
- Links the artist line to the first Yandex Music artist page.

## 0.1.0 - 2026-05-30

First usable version.

- Reads the current Yandex Music track from Windows media sessions.
- Looks up the Yandex Music track, cover, album, and links.
- Shows a Discord Rich Presence card with `Listen` and `Album` buttons.
- Links the title, artist line, and cover when Discord supports field URLs.
- Scores search results so random covers do not sneak in as often.
- Avoids duplicate background processes.
- Adds Startup autostart.
- Adds `--once` and `--doctor`.
- Saves played tracks to `history.csv`.
