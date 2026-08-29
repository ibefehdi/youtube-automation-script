"""Shared topic parsing, API-key checks, and prompt parsers for the pipeline."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCENE_RE = re.compile(r"^Scene\s+(\d+)\s*$", re.IGNORECASE)
PAUSE_RE = re.compile(r"^\((long\s+pause|pause)\)\s*$", re.IGNORECASE)
TOTAL_RE = re.compile(r"^Total Scenes:\s*\d+\s*$", re.IGNORECASE)
NARRATION_RE = re.compile(r"^Narration:\s*(.*)$", re.IGNORECASE)
VISUAL_RE = re.compile(r"^Visual Prompt:\s*(.*)$", re.IGNORECASE)
MOOD_RE = re.compile(r"^Mood:\s*(.*)$", re.IGNORECASE)
CAMERA_RE = re.compile(r"^Camera:\s*(.*)$", re.IGNORECASE)
DURATION_RE = re.compile(r"^Duration:\s*(.*)$", re.IGNORECASE)

PROVIDERS = {
    "elevenlabs": "elevenlabs",
    "11labs": "elevenlabs",
    "eleven": "elevenlabs",
    "heygen": "heygen",
    "hey-gen": "heygen",
    "hey gen": "heygen",
    "piper": "piper",
    "local": "piper",
}

DEFAULT_ELEVEN_VOICE = "adam"
DEFAULT_HEYGEN_VOICE = "documentary"

ELEVENLABS_KEY_NAME = "ELEVENLABS_API_KEY"
HEYGEN_KEY_NAME = "HEYGEN_API_KEY"


def load_dotenv() -> None:
    for path in (ROOT / ".env", ROOT / "tools" / ".env"):
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = value


def env_key(name: str) -> str:
    load_dotenv()
    return os.environ.get(name, "").strip()


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug) or "topic"


def parse_topic(raw: str) -> dict:
    text = " ".join(raw.strip().split())
    tokens = re.split(r"\s+-\s+", text)
    provider = "piper"
    voice = ""
    topic_tokens = tokens

    for i in range(len(tokens) - 1, -1, -1):
        key = tokens[i].strip().lower()
        if key in PROVIDERS:
            provider = PROVIDERS[key]
            voice = " - ".join(tokens[i + 1 :]).strip()
            topic_tokens = tokens[:i]
            break

    topic = " - ".join(topic_tokens).strip() or text
    if provider == "elevenlabs" and not voice:
        voice = DEFAULT_ELEVEN_VOICE
    if provider == "heygen" and not voice:
        voice = DEFAULT_HEYGEN_VOICE
    return {
        "topic": topic,
        "slug": slugify(topic),
        "provider": provider,
        "voice": voice,
    }


def check_keys() -> dict:
    """Report which paid APIs are configured. Presence of a key is not consent."""
    return {
        "elevenlabs": {
            "key": bool(env_key(ELEVENLABS_KEY_NAME)),
            "env": ELEVENLABS_KEY_NAME,
            "voiceover": True,
            "video": False,
        },
        "heygen": {
            "key": bool(env_key(HEYGEN_KEY_NAME)),
            "env": HEYGEN_KEY_NAME,
            "voiceover": True,
            "video": True,
        },
    }


def parse_voiceover(text: str) -> list[dict]:
    lines = text.replace("\r\n", "\n").split("\n")
    scenes: list[dict] = []
    current: dict | None = None
    body: list[str] = []

    def flush() -> None:
        nonlocal current, body
        if current is None:
            return
        narr = " ".join(" ".join(body).split())
        if narr:
            current["text"] = narr
            scenes.append(current)
        current = None
        body = []

    for raw in lines:
        line = raw.strip()
        if not line or TOTAL_RE.match(line):
            continue
        scene_match = SCENE_RE.match(line)
        if scene_match:
            flush()
            current = {"number": int(scene_match.group(1)), "pause": "pause"}
            continue
        pause_match = PAUSE_RE.match(line)
        if pause_match and current is not None:
            kind = pause_match.group(1).lower()
            current["pause"] = "long" if "long" in kind else "pause"
            continue
        if current is not None:
            body.append(line)

    flush()
    if scenes:
        return scenes
    plain = " ".join(text.split())
    if not plain:
        raise SystemExit("No narration text found in input")
    return [{"number": 1, "text": plain, "pause": "pause"}]


def parse_video_prompts(text: str) -> list[dict]:
    lines = text.replace("\r\n", "\n").split("\n")
    scenes: list[dict] = []
    current: dict | None = None
    visual_lines: list[str] = []
    in_visual = False

    def flush() -> None:
        nonlocal current, visual_lines, in_visual
        if current is None:
            return
        visual = " ".join(" ".join(visual_lines).split())
        current["visual"] = visual
        if current.get("narration") or visual:
            scenes.append(current)
        current = None
        visual_lines = []
        in_visual = False

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            if in_visual and visual_lines:
                visual_lines.append("")
            continue
        scene_match = SCENE_RE.match(stripped)
        if scene_match:
            flush()
            current = {
                "number": int(scene_match.group(1)),
                "narration": "",
                "visual": "",
                "mood": "",
                "camera": "",
                "duration": "10 seconds",
            }
            continue
        if current is None:
            continue
        narr = NARRATION_RE.match(stripped)
        if narr:
            in_visual = False
            current["narration"] = narr.group(1).strip()
            continue
        visual = VISUAL_RE.match(stripped)
        if visual:
            in_visual = True
            leftover = visual.group(1).strip()
            visual_lines = [leftover] if leftover else []
            continue
        mood = MOOD_RE.match(stripped)
        if mood:
            in_visual = False
            current["mood"] = mood.group(1).strip()
            continue
        camera = CAMERA_RE.match(stripped)
        if camera:
            in_visual = False
            current["camera"] = camera.group(1).strip()
            continue
        duration = DURATION_RE.match(stripped)
        if duration:
            in_visual = False
            current["duration"] = duration.group(1).strip()
            continue
        if in_visual:
            visual_lines.append(stripped)

    flush()
    if not scenes:
        raise SystemExit("No video prompts found in input")
    return scenes


def print_check_keys() -> None:
    print(json.dumps(check_keys(), indent=2))
