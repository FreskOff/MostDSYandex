import argparse
import asyncio
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

from pypresence import ActivityType, Presence
from yandex_music import Client
from winsdk.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
)


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(__file__)


APP_DIR = app_dir()


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
POLL_SECONDS = max(15, int(os.getenv("POLL_SECONDS", "15")))
IMAGE_SIZE = "400x400"
YANDEX_SOURCES = ("yandex", "music")

# Optional asset keys from the Discord Developer Portal.
FALLBACK_LARGE_IMAGE = os.getenv("DISCORD_FALLBACK_LARGE_IMAGE", "")
SMALL_IMAGE = os.getenv("DISCORD_SMALL_IMAGE", "f")
SMALL_TEXT = os.getenv("DISCORD_SMALL_TEXT", "Playing from Yandex Music")
LISTEN_BUTTON_LABEL = os.getenv("LISTEN_BUTTON_LABEL", "Listen")
ALBUM_BUTTON_LABEL = os.getenv("ALBUM_BUTTON_LABEL", "Album")
PAUSE_BEHAVIOR = os.getenv("PAUSE_BEHAVIOR", "show").lower()
MIN_MATCH_SCORE = int(os.getenv("MIN_MATCH_SCORE", "70"))
HISTORY_ENABLED = os.getenv("HISTORY_ENABLED", "1") != "0"
HISTORY_PATH = os.path.join(APP_DIR, "history.csv")


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
    if not track.is_playing and PAUSE_BEHAVIOR == "show":
        state = f"Paused - {state}"[:128]
        large_text = f"Paused on Yandex Music"

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
                "Where-Object { $_.CommandLine -and $_.CommandLine.Contains($n) -and "
                "$_.ProcessId -ne $pidToSkip -and "
                "$_.CommandLine -notmatch '--once|--doctor' -and "
                "($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') } | "
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
    print(f"album_title: {meta.album_title or 'missing'}")
    print(f"match: {meta.matched_artist or '-'} - {meta.matched_title or '-'} ({meta.score})")


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


def run_presence() -> None:
    if not CLIENT_ID:
        raise RuntimeError("Set DISCORD_CLIENT_ID or edit CLIENT_ID in presence.py.")

    resolver = CoverResolver()
    rpc = Presence(CLIENT_ID)
    print("Connecting to Discord...")
    rpc.connect()
    print("Connected. Start Yandex Music playback and leave this window open.")

    last_signature = ""
    current_started_at: Optional[int] = None
    last_history_key = ""

    while True:
        try:
            track = asyncio.run(get_yandex_track())
            if not track:
                if last_signature:
                    rpc.clear()
                    last_signature = ""
                    current_started_at = None
                    print("[discord] cleared: Yandex Music session not found")
                time.sleep(POLL_SECONDS)
                continue

            if not track.is_playing and PAUSE_BEHAVIOR == "clear":
                if last_signature:
                    rpc.clear()
                    last_signature = ""
                    current_started_at = None
                    print("[discord] cleared: playback paused")
                time.sleep(POLL_SECONDS)
                continue

            signature = f"{track.key}::{track.is_playing}::{track.duration_seconds}"
            if signature != last_signature:
                if track.is_playing:
                    current_started_at = int(time.time()) - track.position_seconds
                else:
                    current_started_at = None

                meta = resolver.resolve(track)
                payload = build_presence_payload(track, meta, current_started_at)
                rpc.update(**payload)

                print(f"[discord] {track.artist} - {track.title}")
                print(f"[cover] {meta.cover_url or FALLBACK_LARGE_IMAGE or 'fallback missing'}")
                print(f"[url] {meta.track_url or 'missing'}")
                print(f"[album] {meta.album_url or 'missing'}")
                print(f"[match] {meta.matched_artist or '-'} - {meta.matched_title or '-'} ({meta.score})")
                if track.is_playing and track.key != last_history_key:
                    append_history(track, meta)
                    last_history_key = track.key
                last_signature = signature

        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"[loop] {exc}")

        time.sleep(POLL_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Yandex Music -> Discord Rich Presence bridge")
    parser.add_argument("--once", action="store_true", help="print detected track and cover, then exit")
    parser.add_argument("--doctor", action="store_true", help="run diagnostics and exit")
    args = parser.parse_args()

    if args.doctor:
        doctor()
    elif args.once:
        asyncio.run(print_once())
    else:
        try:
            run_presence()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
