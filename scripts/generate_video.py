#!/usr/bin/env python3
"""Generate scene clips with HeyGen when HEYGEN_API_KEY is set.

The AI asks yes/no in chat before calling this script. The script
itself does not prompt.

Resume is stored in SQLite next to the clips. Re-run the same command
to continue unfinished scenes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

from generate_voiceover import (
    download_bytes,
    heygen_error_detail,
    heygen_json,
    heygen_key,
)
from pipeline_lib import env_key, parse_topic, parse_video_prompts, print_check_keys

POLL_SESSION_SEC = 8
POLL_VIDEO_SEC = 15
SESSION_TIMEOUT_SEC = 45 * 60
VIDEO_TIMEOUT_SEC = 45 * 60


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def scene_fingerprint(scene: dict) -> str:
    blob = json.dumps(
        {
            "narration": scene.get("narration") or "",
            "visual": scene.get("visual") or "",
            "mood": scene.get("mood") or "",
            "camera": scene.get("camera") or "",
        },
        sort_keys=True,
    )
    return text_hash(blob)


def connect_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS job (
            id INTEGER PRIMARY KEY,
            input_path TEXT NOT NULL,
            input_hash TEXT NOT NULL,
            provider TEXT NOT NULL,
            voice TEXT NOT NULL,
            settings_json TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS scene (
            job_id INTEGER NOT NULL,
            scene_number INTEGER NOT NULL,
            text_hash TEXT NOT NULL,
            status TEXT NOT NULL,
            video_path TEXT,
            session_id TEXT,
            video_id TEXT,
            error TEXT,
            duration_sec REAL,
            PRIMARY KEY (job_id, scene_number),
            FOREIGN KEY (job_id) REFERENCES job(id)
        );
        """
    )
    conn.commit()
    return conn


def get_or_create_job(
    conn: sqlite3.Connection,
    input_path: Path,
    input_hash: str,
    settings: dict,
) -> int:
    settings_json = json.dumps(settings, sort_keys=True)
    row = conn.execute(
        """
        SELECT id FROM job
        WHERE input_path = ? AND input_hash = ? AND provider = 'heygen'
          AND settings_json = ?
        ORDER BY id DESC LIMIT 1
        """,
        (str(input_path), input_hash, settings_json),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE job SET status = ?, updated_at = ? WHERE id = ?",
            ("running", now_iso(), row["id"]),
        )
        conn.commit()
        return int(row["id"])
    cur = conn.execute(
        """
        INSERT INTO job (input_path, input_hash, provider, voice, settings_json, status, created_at, updated_at)
        VALUES (?, ?, 'heygen', '', ?, 'running', ?, ?)
        """,
        (str(input_path), input_hash, settings_json, now_iso(), now_iso()),
    )
    conn.commit()
    return int(cur.lastrowid)


def scene_row(conn: sqlite3.Connection, job_id: int, number: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM scene WHERE job_id = ? AND scene_number = ?",
        (job_id, number),
    ).fetchone()


def mark_scene(
    conn: sqlite3.Connection,
    job_id: int,
    number: int,
    thash: str,
    status: str,
    video_path: str | None,
    session_id: str | None,
    video_id: str | None,
    error: str | None,
    duration: float | None,
) -> None:
    conn.execute(
        """
        INSERT INTO scene (
            job_id, scene_number, text_hash, status, video_path,
            session_id, video_id, error, duration_sec
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_id, scene_number) DO UPDATE SET
            text_hash = excluded.text_hash,
            status = excluded.status,
            video_path = excluded.video_path,
            session_id = excluded.session_id,
            video_id = excluded.video_id,
            error = excluded.error,
            duration_sec = excluded.duration_sec
        """,
        (job_id, number, thash, status, video_path, session_id, video_id, error, duration),
    )
    conn.execute("UPDATE job SET updated_at = ? WHERE id = ?", (now_iso(), job_id))
    conn.commit()


def agent_prompt(scene: dict, title: str) -> str:
    narration = (scene.get("narration") or "").strip()
    visual = (scene.get("visual") or "").strip()
    mood = (scene.get("mood") or "dark, documentary").strip()
    camera = (scene.get("camera") or "slow, steady").strip()
    duration = (scene.get("duration") or "10 seconds").strip()
    return (
        f"Create one {duration} landscape true-crime documentary clip titled {title}. "
        "No on-screen text, captions, logos, titles, or lower-thirds.\n\n"
        "Speak this narration word-for-word and nothing else:\n"
        f'"""{narration}"""\n\n'
        f"Visual direction:\n{visual}\n\n"
        f"Mood: {mood}\n"
        f"Camera: {camera}\n\n"
        "Do not invent extra spoken lines. Dark, desaturated, cinematic documentary. No gore."
    )[:10000]


def unwrap(payload: dict) -> dict:
    data = payload.get("data")
    return data if isinstance(data, dict) else payload


def start_session(key: str, prompt: str, voice_id: str) -> str:
    body: dict = {
        "prompt": prompt,
        "mode": "generate",
        "orientation": "landscape",
    }
    if voice_id:
        body["voice_id"] = voice_id
    payload = heygen_json("POST", "https://api.heygen.com/v3/video-agents", key, body)
    data = unwrap(payload)
    session_id = str(data.get("session_id") or "")
    if not session_id:
        raise SystemExit(f"HeyGen video-agent response had no session_id: {payload}")
    return session_id


def poll_session(key: str, session_id: str) -> str:
    deadline = time.time() + SESSION_TIMEOUT_SEC
    while time.time() < deadline:
        payload = heygen_json("GET", f"https://api.heygen.com/v3/video-agents/{session_id}", key)
        data = unwrap(payload)
        status = str(data.get("status") or "").lower()
        video_id = str(data.get("video_id") or "")
        if video_id:
            return video_id
        if status == "failed":
            raise RuntimeError(data.get("failure_message") or data.get("error") or "session failed")
        time.sleep(POLL_SESSION_SEC)
    raise RuntimeError(f"Timed out waiting for HeyGen session {session_id}")


def poll_video(key: str, video_id: str) -> dict:
    deadline = time.time() + VIDEO_TIMEOUT_SEC
    while time.time() < deadline:
        payload = heygen_json("GET", f"https://api.heygen.com/v3/videos/{video_id}", key)
        data = unwrap(payload)
        status = str(data.get("status") or "").lower()
        if status == "completed":
            return data
        if status == "failed":
            raise RuntimeError(data.get("failure_message") or data.get("failure_code") or "video failed")
        time.sleep(POLL_VIDEO_SEC)
    raise RuntimeError(f"Timed out waiting for HeyGen video {video_id}")


def finish_clip(key: str, session_id: str | None, video_id: str | None, dest: Path) -> tuple[str, str, float]:
    vid = video_id or ""
    if not vid:
        if not session_id:
            raise RuntimeError("No HeyGen session_id or video_id to resume")
        vid = poll_session(key, session_id)
    data = poll_video(key, vid)
    url = str(data.get("video_url") or "")
    if not url:
        raise RuntimeError(f"HeyGen video {vid} completed without video_url")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(download_bytes(url, timeout=300))
    duration = float(data.get("duration") or 0)
    return session_id or "", vid, duration


def parse_scene_range(raw: str | None, total: int) -> list[int]:
    if not raw:
        return list(range(1, total + 1))
    wanted: set[int] = set()
    for part in raw.split(","):
        piece = part.strip()
        if not piece:
            continue
        if "-" in piece:
            start_s, end_s = piece.split("-", 1)
            start, end = int(start_s), int(end_s)
            wanted.update(range(start, end + 1))
        else:
            wanted.add(int(piece))
    return [n for n in range(1, total + 1) if n in wanted]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate HeyGen video clips from 04-video-prompts.md")
    parser.add_argument("input", nargs="?", help="04-video-prompts.md")
    parser.add_argument("--check-keys", action="store_true", help="Print which paid API keys are set and exit")
    parser.add_argument("--from-topic", help="Raw user topic, used only for the output folder default")
    parser.add_argument("--output-dir", help="Directory for MP4 files")
    parser.add_argument("--voice", default="", help="Optional HeyGen voice ID for Video Agent narration")
    parser.add_argument("--scenes", help="Scene numbers to render, e.g. 1-5 or 3,8,12")
    parser.add_argument("--max-scenes", type=int, default=0, help="Stop after this many new renders (0 = all)")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.check_keys:
        print_check_keys()
        return 0

    if not args.input:
        parser.error("Pass a video-prompts file")

    if not env_key("HEYGEN_API_KEY"):
        raise SystemExit(
            "HeyGen video requested but HEYGEN_API_KEY is missing.\n"
            "Add it with: export HEYGEN_API_KEY=...   or put it in .env"
        )

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        raise SystemExit(f"Input not found: {input_path}")

    topic_meta = parse_topic(args.from_topic) if args.from_topic else None
    out_dir = Path(args.output_dir) if args.output_dir else input_path.parent / "video"
    out_dir.mkdir(parents=True, exist_ok=True)

    source_text = input_path.read_text(encoding="utf-8")
    scenes = parse_video_prompts(source_text)
    by_number = {scene["number"]: scene for scene in scenes}
    selected = parse_scene_range(args.scenes, max(by_number) if by_number else 0)
    todo = [by_number[n] for n in selected if n in by_number]
    if not todo:
        raise SystemExit("No matching scenes to render")

    title = topic_meta["topic"] if topic_meta else input_path.parent.name
    settings = {"mode": "video-agent", "orientation": "landscape", "voice": args.voice or ""}
    print(
        f"HeyGen video: {len(todo)} scene(s). Each clip can take several minutes "
        "and uses HeyGen credits."
    )

    key = heygen_key()
    conn = connect_db(out_dir / "progress.sqlite")
    job_id = get_or_create_job(conn, input_path, text_hash(source_text), settings)
    print(f"Job {job_id}  resume db {out_dir / 'progress.sqlite'}")

    generated = 0
    skipped = 0
    failed = 0
    rendered_now = 0

    for scene in todo:
        number = scene["number"]
        thash = scene_fingerprint(scene)
        clip_name = f"scene-{number:03d}.mp4"
        clip_path = out_dir / clip_name
        row = scene_row(conn, job_id, number)

        if (
            not args.force
            and clip_path.exists()
            and clip_path.stat().st_size > 1000
            and row
            and row["status"] == "done"
            and row["text_hash"] == thash
        ):
            skipped += 1
            print(f"  skip  {number:03d}  already done")
            continue

        if args.max_scenes and rendered_now >= args.max_scenes:
            print(f"Reached --max-scenes {args.max_scenes}. Re-run to continue.")
            break

        session_id = str(row["session_id"] or "") if row and row["text_hash"] == thash else ""
        video_id = str(row["video_id"] or "") if row and row["text_hash"] == thash else ""
        try:
            if not session_id and not video_id:
                prompt = agent_prompt(scene, f"{title} scene {number:03d}")
                session_id = start_session(key, prompt, args.voice)
                mark_scene(
                    conn, job_id, number, thash, "submitted", None, session_id, None, None, None
                )
                print(f"  start {number:03d}  session {session_id}")
            session_id, video_id, duration = finish_clip(key, session_id, video_id, clip_path)
            mark_scene(
                conn,
                job_id,
                number,
                thash,
                "done",
                str(clip_path),
                session_id,
                video_id,
                None,
                duration,
            )
            generated += 1
            rendered_now += 1
            print(f"  scene {number:03d}  {duration:5.1f}s  {clip_path.name}")
        except SystemExit:
            raise
        except urllib.error.HTTPError as exc:
            failed += 1
            detail = heygen_error_detail(exc)
            mark_scene(conn, job_id, number, thash, "failed", None, session_id, video_id, detail, None)
            print(f"  FAIL  {number:03d}  HTTP {exc.code}: {detail}")
        except Exception as exc:
            failed += 1
            mark_scene(conn, job_id, number, thash, "failed", None, session_id, video_id, str(exc), None)
            print(f"  FAIL  {number:03d}  {exc}")

    status = "failed" if failed else "done"
    conn.execute("UPDATE job SET status = ?, updated_at = ? WHERE id = ?", (status, now_iso(), job_id))
    conn.commit()
    conn.close()
    print(f"Wrote clips under {out_dir}  generated {generated}  skipped {skipped}  failed {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
