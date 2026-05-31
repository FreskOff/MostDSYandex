import argparse
import asyncio
import ctypes
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

from pypresence import ActivityType, Presence
from pypresence.payloads import Payload
from yandex_music import Client
from winsdk.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
)


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(__file__)


APP_DIR = app_dir()
RESOURCE_DIR = getattr(sys, "_MEIPASS", APP_DIR)


def load_env_file(path: str) -> None:
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


load_env_file(os.path.join(APP_DIR, ".env"))


CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "1504152588684230656")
POLL_SECONDS = max(1, int(os.getenv("POLL_SECONDS", "2")))
IMAGE_SIZE = "400x400"
YANDEX_SOURCES = ("yandex", "music")

# Optional asset keys from the Discord Developer Portal.
FALLBACK_LARGE_IMAGE = os.getenv("DISCORD_FALLBACK_LARGE_IMAGE", "")
SMALL_IMAGE = os.getenv("DISCORD_SMALL_IMAGE", "f")
SMALL_TEXT = os.getenv("DISCORD_SMALL_TEXT", "Playing from Yandex Music")
LISTEN_BUTTON_LABEL = os.getenv("LISTEN_BUTTON_LABEL", "Listen")
ALBUM_BUTTON_LABEL = os.getenv("ALBUM_BUTTON_LABEL", "Album")
PAUSE_BEHAVIOR = os.getenv("PAUSE_BEHAVIOR", "clear").lower()
MIN_MATCH_SCORE = int(os.getenv("MIN_MATCH_SCORE", "70"))
HISTORY_ENABLED = os.getenv("HISTORY_ENABLED", "1") != "0"
HISTORY_PATH = os.path.join(APP_DIR, "history.csv")
ICON_PATH = os.path.join(RESOURCE_DIR, "assets", "app-icon.png")
ICO_PATH = os.path.join(RESOURCE_DIR, "assets", "app-icon.ico")


class RuntimeState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.status = "Starting"
        self.track = ""
        self.cover_url = ""
        self.track_url = ""
        self.artist_url = ""
        self.album_url = ""
        self.last_error = ""

    def update(self, **values: str) -> None:
        with self.lock:
            for key, value in values.items():
                setattr(self, key, value or "")

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "status": self.status,
                "track": self.track,
                "cover_url": self.cover_url,
                "track_url": self.track_url,
                "artist_url": self.artist_url,
                "album_url": self.album_url,
                "last_error": self.last_error,
            }


RUNTIME = RuntimeState()
_SINGLE_INSTANCE_MUTEX = None


def acquire_single_instance() -> bool:
    global _SINGLE_INSTANCE_MUTEX
    kernel32 = ctypes.windll.kernel32
    _SINGLE_INSTANCE_MUTEX = kernel32.CreateMutexW(None, False, "Local\\MostDSYandex.Tray")
    return kernel32.GetLastError() != 183


@dataclass(frozen=True)
class Track:
    title: str
    artist: str
    album: str = ""
    source: str = ""
    duration_seconds: int = 0
    position_seconds: int = 0
    is_playing: bool = True

    @property
    def key(self) -> str:
        return f"{self.artist.lower()}::{self.title.lower()}"


@dataclass(frozen=True)
class TrackMeta:
    cover_url: Optional[str] = None
    track_url: Optional[str] = None
    album_url: Optional[str] = None
    artist_url: Optional[str] = None
    album_title: str = ""
    matched_title: str = ""
    matched_artist: str = ""
    score: int = 0


def normalize(text: str) -> str:
    text = text.lower().replace("ё", "е")
    text = re.sub(r"\([^)]*\)|\[[^]]*]", " ", text)
    text = re.sub(r"[^a-zа-я0-9]+", " ", text)
    return " ".join(text.split())


def similarity_score(left: str, right: str) -> int:
    left_norm = normalize(left)
    right_norm = normalize(right)
    if not left_norm or not right_norm:
        return 0
    if left_norm == right_norm:
        return 45
    if left_norm in right_norm or right_norm in left_norm:
        return 30
    left_words = set(left_norm.split())
    right_words = set(right_norm.split())
    overlap = len(left_words & right_words)
    total = max(len(left_words | right_words), 1)
    return int(25 * overlap / total)


def track_artists(candidate) -> str:
    artists = getattr(candidate, "artists", None) or []
    return ", ".join(getattr(artist, "name", "") for artist in artists).strip()


def candidate_duration_seconds(candidate) -> int:
    duration_ms = getattr(candidate, "duration_ms", None) or getattr(candidate, "durationMs", None)
    return int(duration_ms / 1000) if duration_ms else 0


def score_candidate(source: Track, candidate) -> int:
    score = similarity_score(source.title, getattr(candidate, "title", "") or "")
    score += similarity_score(source.artist, track_artists(candidate))

    candidate_duration = candidate_duration_seconds(candidate)
    if source.duration_seconds and candidate_duration:
        delta = abs(source.duration_seconds - candidate_duration)
        if delta <= 2:
            score += 25
        elif delta <= 6:
            score += 15
        elif delta <= 15:
            score += 5
        else:
            score -= 15

    return score


class CoverResolver:
    def __init__(self) -> None:
        self.client = Client().init()
        self.cache: dict[str, TrackMeta] = {}

    def resolve(self, track: Track) -> TrackMeta:
        if track.key in self.cache:
            return self.cache[track.key]

        query = " ".join(part for part in (track.artist, track.title) if part).strip()
        if not query:
            self.cache[track.key] = TrackMeta()
            return self.cache[track.key]

        cover_url = None
        track_url = None
        album_url = None
        artist_url = None
        album_title = ""
        try:
            result = self.client.search(query, type_="track")
            tracks = result.tracks.results[:10] if result and result.tracks else []
            best = max(tracks, key=lambda item: score_candidate(track, item), default=None)
            best_score = score_candidate(track, best) if best else 0
            if best and best_score >= MIN_MATCH_SCORE and best.cover_uri:
                cover_url = best.get_cover_url(IMAGE_SIZE)
            if best and best_score >= MIN_MATCH_SCORE and best.id and best.albums:
                album = best.albums[0]
                album_id = album.id
                album_title = getattr(album, "title", "") or ""
                track_url = f"https://music.yandex.ru/album/{album_id}/track/{best.id}"
                album_url = f"https://music.yandex.ru/album/{album_id}"
            if best and best_score >= MIN_MATCH_SCORE and best.artists:
                artist_id = getattr(best.artists[0], "id", None)
                if artist_id:
                    artist_url = f"https://music.yandex.ru/artist/{artist_id}"
            matched_title = getattr(best, "title", "") if best else ""
            matched_artist = track_artists(best) if best else ""
        except Exception as exc:
            print(f"[cover] search failed: {exc}")
            matched_title = ""
            matched_artist = ""
            best_score = 0
            album_title = ""

        self.cache[track.key] = TrackMeta(
            cover_url=cover_url,
            track_url=track_url,
            album_url=album_url,
            artist_url=artist_url,
            album_title=album_title,
            matched_title=matched_title,
            matched_artist=matched_artist,
            score=best_score,
        )
        return self.cache[track.key]


async def get_yandex_track() -> Optional[Track]:
    manager = await MediaManager.request_async()
    sessions = list(manager.get_sessions())
    current = manager.get_current_session()

    ordered_sessions = []
    if current:
        ordered_sessions.append(current)
    ordered_sessions.extend(session for session in sessions if session != current)

    for session in ordered_sessions:
        source = (session.source_app_user_model_id or "").lower()
        if not all(token in source for token in YANDEX_SOURCES):
            continue

        props = await session.try_get_media_properties_async()
        title = (props.title or "").strip()
        artist = (props.artist or "").strip()
        album = (props.album_title or "").strip()

        if not title:
            continue

        timeline = session.get_timeline_properties()
        playback = session.get_playback_info()
        status_name = getattr(playback.playback_status, "name", str(playback.playback_status))

        return Track(
            title=title,
            artist=artist or "Yandex Music",
            album=album,
            source=session.source_app_user_model_id,
            duration_seconds=max(0, int(timeline.end_time.total_seconds())),
            position_seconds=max(0, int(timeline.position.total_seconds())),
            is_playing=status_name.upper().endswith("PLAYING") or str(playback.playback_status) == "4",
        )

    return None


def build_presence_payload(track: Track, meta: TrackMeta, started_at: Optional[int]) -> dict:
    large_image = meta.cover_url or FALLBACK_LARGE_IMAGE or None
    start = started_at if track.is_playing else None
    end = start + track.duration_seconds if start and track.duration_seconds else None
    state = track.artist[:128] or "Yandex Music"
    large_text = meta.album_title or track.album or f"{track.title} - {track.artist}"

    buttons = []
    if meta.track_url:
        buttons.append({"label": LISTEN_BUTTON_LABEL, "url": meta.track_url})
    if meta.album_url:
        buttons.append({"label": ALBUM_BUTTON_LABEL, "url": meta.album_url})

    payload = {
        "activity_type": ActivityType.LISTENING,
        "details": track.title[:128],
        "state": state,
        "large_image": large_image,
        "large_text": large_text[:128],
        "small_image": SMALL_IMAGE or None,
        "small_text": SMALL_TEXT,
        "start": start,
        "end": end,
        "buttons": buttons or None,
    }
    return {key: value for key, value in payload.items() if value is not None}


async def print_once() -> None:
    track = await get_yandex_track()
    if not track:
        print("No Yandex Music media session found.")
        return

    meta = CoverResolver().resolve(track)
    print(f"source: {track.source}")
    print(f"title: {track.title}")
    print(f"artist: {track.artist}")
    print(f"album: {track.album or '-'}")
    print(f"position: {track.position_seconds}s / {track.duration_seconds}s")
    print(f"playing: {track.is_playing}")
    print(f"cover: {meta.cover_url or '-'}")
    print(f"url: {meta.track_url or '-'}")
    print(f"album_url: {meta.album_url or '-'}")
    print(f"artist_url: {meta.artist_url or '-'}")
    print(f"album_title: {meta.album_title or '-'}")
    print(f"match: {meta.matched_artist or '-'} - {meta.matched_title or '-'} ({meta.score})")


def csv_escape(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def append_history(track: Track, meta: TrackMeta) -> None:
    if not HISTORY_ENABLED:
        return

    exists = os.path.exists(HISTORY_PATH)
    line = ",".join(
        csv_escape(value)
        for value in [
            datetime.now().isoformat(timespec="seconds"),
            track.title,
            track.artist,
            meta.album_title or track.album,
            meta.track_url or "",
            meta.album_url or "",
            str(meta.score),
        ]
    )
    with open(HISTORY_PATH, "a", encoding="utf-8", newline="") as file:
        if not exists:
            file.write('"played_at","title","artist","album","track_url","album_url","match_score"\n')
        file.write(line + "\n")


def count_presence_processes() -> int:
    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                f"$n='presence.py'; $pidToSkip={os.getpid()}; "
                "Get-CimInstance Win32_Process | "
                "Where-Object { $_.ProcessId -ne $pidToSkip -and ("
                "$_.Name -eq 'MostDSYandex.exe' -or "
                "($_.CommandLine -and $_.CommandLine.Contains($n) -and "
                "$_.CommandLine -notmatch '--once|--doctor' -and "
                "($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe'))) } | "
                "Measure-Object | Select-Object -ExpandProperty Count",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return int((result.stdout or "0").strip() or "0")
    except Exception:
        return -1


async def doctor_media() -> None:
    track = await get_yandex_track()
    if not track:
        print("media_session: missing")
        return

    print("media_session: ok")
    print(f"source: {track.source}")
    print(f"track: {track.artist} - {track.title}")
    print(f"duration: {track.position_seconds}s / {track.duration_seconds}s")
    print(f"playing: {track.is_playing}")

    meta = CoverResolver().resolve(track)
    print(f"cover: {meta.cover_url or 'missing'}")
    print(f"url: {meta.track_url or 'missing'}")
    print(f"album_url: {meta.album_url or 'missing'}")
    print(f"artist_url: {meta.artist_url or 'missing'}")
    print(f"album_title: {meta.album_title or 'missing'}")
    print(f"match: {meta.matched_artist or '-'} - {meta.matched_title or '-'} ({meta.score})")


def update_discord_activity(rpc: Presence, payload: dict, meta: TrackMeta) -> None:
    activity_payload = Payload.set_activity(
        pid=os.getpid(),
        activity_type=payload.get("activity_type"),
        state=payload.get("state"),
        details=payload.get("details"),
        start=(int(payload["start"]) * 1000) if payload.get("start") else None,
        end=(int(payload["end"]) * 1000) if payload.get("end") else None,
        large_image=payload.get("large_image"),
        large_text=payload.get("large_text"),
        small_image=payload.get("small_image"),
        small_text=payload.get("small_text"),
        buttons=payload.get("buttons"),
        instance=True,
        activity=True,
    )
    activity = activity_payload.data["args"]["activity"]

    if meta.track_url:
        activity["details_url"] = meta.track_url
        activity["assets"]["large_url"] = meta.track_url
    if meta.artist_url:
        activity["state_url"] = meta.artist_url
    elif meta.track_url:
        activity["state_url"] = meta.track_url

    rpc.update(payload_override=activity_payload)


def doctor() -> None:
    print("MostDSYandex doctor")
    print(f"python: ok")
    print(f"client_id: {CLIENT_ID}")
    print(f"poll_seconds: {POLL_SECONDS}")
    print(f"pause_behavior: {PAUSE_BEHAVIOR}")
    print(f"min_match_score: {MIN_MATCH_SCORE}")
    print(f"history: {'on' if HISTORY_ENABLED else 'off'}")

    startup = os.path.join(
        os.environ["APPDATA"],
        "Microsoft",
        "Windows",
        "Start Menu",
        "Programs",
        "Startup",
        "MostDSYandex Presence.lnk",
    )
    print(f"autostart: {'ok' if os.path.exists(startup) else 'missing'}")
    process_count = count_presence_processes()
    print(f"presence_processes: {process_count if process_count >= 0 else 'unknown'}")

    asyncio.run(doctor_media())

    try:
        rpc = Presence(CLIENT_ID)
        rpc.connect()
        rpc.close()
        print("discord_rpc: ok")
    except Exception as exc:
        print(f"discord_rpc: failed ({exc})")


def run_presence(stop_event: Optional[threading.Event] = None, runtime: Optional[RuntimeState] = None) -> None:
    if not CLIENT_ID:
        raise RuntimeError("Set DISCORD_CLIENT_ID or edit CLIENT_ID in presence.py.")

    stop_event = stop_event or threading.Event()
    runtime = runtime or RUNTIME
    resolver = CoverResolver()
    rpc = Presence(CLIENT_ID)
    print("Connecting to Discord...")
    runtime.update(status="Connecting to Discord")
    rpc.connect()
    print("Connected. Start Yandex Music playback and leave this window open.")
    runtime.update(status="Running", last_error="")

    last_signature = ""
    current_started_at: Optional[int] = None
    last_history_key = ""

    while not stop_event.is_set():
        try:
            track = asyncio.run(get_yandex_track())
            if not track:
                if last_signature:
                    rpc.clear()
                    last_signature = ""
                    current_started_at = None
                    print("[discord] cleared: Yandex Music session not found")
                runtime.update(status="Waiting for Yandex Music", track="")
                stop_event.wait(POLL_SECONDS)
                continue

            if not track.is_playing and PAUSE_BEHAVIOR == "clear":
                rpc.clear()
                last_signature = ""
                current_started_at = None
                print("[discord] cleared: playback paused")
                runtime.update(status="Paused", track=f"{track.artist} - {track.title}")
                stop_event.wait(POLL_SECONDS)
                continue

            signature = f"{track.key}::{track.is_playing}::{track.duration_seconds}"
            if signature != last_signature:
                if track.is_playing:
                    current_started_at = int(time.time()) - track.position_seconds
                else:
                    current_started_at = None

                meta = resolver.resolve(track)
                payload = build_presence_payload(track, meta, current_started_at)
                update_discord_activity(rpc, payload, meta)

                print(f"[discord] {track.artist} - {track.title}")
                print(f"[cover] {meta.cover_url or FALLBACK_LARGE_IMAGE or 'fallback missing'}")
                print(f"[url] {meta.track_url or 'missing'}")
                print(f"[album] {meta.album_url or 'missing'}")
                print(f"[artist] {meta.artist_url or 'missing'}")
                print(f"[match] {meta.matched_artist or '-'} - {meta.matched_title or '-'} ({meta.score})")
                runtime.update(
                    status="Playing" if track.is_playing else "Paused",
                    track=f"{track.artist} - {track.title}",
                    cover_url=meta.cover_url or "",
                    track_url=meta.track_url or "",
                    artist_url=meta.artist_url or "",
                    album_url=meta.album_url or "",
                    last_error="",
                )
                if track.is_playing and track.key != last_history_key:
                    append_history(track, meta)
                    last_history_key = track.key
                last_signature = signature

        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"[loop] {exc}")
            runtime.update(status="Error", last_error=str(exc))

        stop_event.wait(POLL_SECONDS)

    try:
        rpc.clear()
        rpc.close()
    except Exception:
        pass
    runtime.update(status="Stopped")


def open_path(path: str) -> None:
    if path.startswith("http://") or path.startswith("https://"):
        os.startfile(path)
        return
    if os.path.exists(path):
        os.startfile(path)


def run_tray() -> None:
    if not acquire_single_instance():
        return

    try:
        import pystray
        from PIL import Image, ImageDraw, ImageTk
        import tkinter as tk
    except Exception as exc:
        print(f"Tray dependencies are missing: {exc}")
        run_presence()
        return

    stop_event = threading.Event()
    worker = threading.Thread(target=run_presence, args=(stop_event, RUNTIME), daemon=True)
    worker.start()

    def load_icon_image():
        if os.path.exists(ICON_PATH):
            return Image.open(ICON_PATH).convert("RGBA")
        image = Image.new("RGBA", (64, 64), (18, 18, 24, 255))
        draw = ImageDraw.Draw(image)
        draw.ellipse((10, 10, 54, 54), fill=(255, 210, 0, 255))
        draw.ellipse((24, 24, 56, 56), fill=(88, 101, 242, 255))
        draw.ellipse((44, 44, 58, 58), fill=(35, 209, 96, 255))
        return image

    def show_status():
        snap = RUNTIME.snapshot()
        root = tk.Tk()
        root.title("MostDSYandex")
        root.geometry("380x230")
        root.resizable(False, False)
        if os.path.exists(ICO_PATH):
            root.iconbitmap(ICO_PATH)

        bg = "#0f1117"
        panel = "#171a22"
        fg = "#f5f7fb"
        muted = "#9aa3b2"
        accent = "#ffd22e"
        border = "#252a35"
        root.configure(bg=bg)

        frame = tk.Frame(root, bg=panel, padx=18, pady=16, highlightbackground=border, highlightthickness=1)
        frame.pack(fill="both", expand=True, padx=14, pady=14)

        header = tk.Frame(frame, bg=panel)
        header.pack(fill="x")

        if os.path.exists(ICON_PATH):
            icon_img = Image.open(ICON_PATH).resize((36, 36), Image.Resampling.LANCZOS)
            icon_photo = ImageTk.PhotoImage(icon_img)
            icon_label = tk.Label(header, image=icon_photo, bg=panel)
            icon_label.image = icon_photo
            icon_label.pack(side="left", padx=(0, 10))

        title_block = tk.Frame(header, bg=panel)
        title_block.pack(side="left", fill="x", expand=True)
        tk.Label(title_block, text="MostDSYandex", bg=panel, fg=fg, font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(title_block, text=snap["status"], bg=panel, fg=accent, font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(1, 0))

        tk.Label(
            frame,
            text=snap["track"] or "Waiting for Yandex Music",
            bg=panel,
            fg=fg,
            font=("Segoe UI", 10),
            wraplength=320,
            justify="left",
        ).pack(anchor="w", pady=(18, 0))

        subtext = "Discord card is active" if snap["status"] == "Playing" else "Status is hidden while playback is paused"
        tk.Label(frame, text=subtext, bg=panel, fg=muted, font=("Segoe UI", 9)).pack(anchor="w", pady=(6, 0))

        if snap["last_error"]:
            tk.Label(frame, text=snap["last_error"], bg=panel, fg="#ff8a8a", font=("Segoe UI", 9), wraplength=360, justify="left").pack(anchor="w", pady=(12, 0))

        buttons = tk.Frame(frame, bg=panel)
        buttons.pack(fill="x", side="bottom", pady=(16, 0))

        def button(parent, text, command):
            return tk.Button(
                parent,
                text=text,
                command=command,
                bg="#222733",
                fg=fg,
                activebackground="#2c3342",
                activeforeground=fg,
                relief="flat",
                bd=0,
                padx=14,
                pady=7,
                font=("Segoe UI", 9),
            )

        if snap["track_url"]:
            button(buttons, "Open track", lambda: open_path(snap["track_url"])).pack(side="left")
        button(buttons, "Folder", lambda: open_path(APP_DIR)).pack(side="left", padx=(8, 0))
        button(buttons, "Close", root.destroy).pack(side="right")
        root.mainloop()

    def quit_app(icon, _item=None):
        stop_event.set()
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Status", lambda icon, item: threading.Thread(target=show_status, daemon=True).start(), default=True),
        pystray.MenuItem("Open folder", lambda icon, item: open_path(APP_DIR)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", quit_app),
    )

    icon = pystray.Icon("MostDSYandex", load_icon_image(), "MostDSYandex", menu)
    icon.run()
    stop_event.set()


def main() -> None:
    parser = argparse.ArgumentParser(description="Yandex Music -> Discord Rich Presence bridge")
    parser.add_argument("--once", action="store_true", help="print detected track and cover, then exit")
    parser.add_argument("--doctor", action="store_true", help="run diagnostics and exit")
    parser.add_argument("--tray", action="store_true", help="run as a tray utility")
    parser.add_argument("--console", action="store_true", help="force console mode when running the exe")
    args = parser.parse_args()

    if args.doctor:
        doctor()
    elif args.once:
        asyncio.run(print_once())
    elif args.tray or (getattr(sys, "frozen", False) and not args.console):
        run_tray()
    else:
        try:
            run_presence()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
