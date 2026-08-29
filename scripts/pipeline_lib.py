"""Shared topic parsing, API-key checks, and prompt parsers for the pipeline."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
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
    "kokoro": "kokoro",
    "chatterbox": "chatterbox",
    "orpheus": "orpheus",
    "local": "chatterbox",
}

DEFAULT_LOCAL_PROVIDER = "chatterbox"
DEFAULT_ELEVEN_VOICE = "adam"
DEFAULT_HEYGEN_VOICE = "documentary"
DEFAULT_KOKORO_VOICE = "am_michael"
DEFAULT_ORPHEUS_VOICE = "dan"
DEFAULT_CHATTERBOX_EXAGGERATION = 0.4
DEFAULT_CHATTERBOX_CFG = 0.45

LOCAL_TORCH_PROVIDERS = frozenset({"kokoro", "chatterbox", "orpheus"})
PAID_PROVIDERS = frozenset({"elevenlabs", "heygen"})

PIPER_ENV = ROOT / "tools" / "piper-env"
TTS_ENV = ROOT / "tools" / "tts-env"
PIPER_VOICES = ROOT / "tools" / "piper-voices"
NARRATOR_WAV = ROOT / "tools" / "voices" / "narrator.wav"

# User-facing sound menu. `say` is what the AI reads aloud. `provider` is internal.
VOICE_INTENTS: list[dict] = [
    {
        "id": "rumble",
        "provider": "piper",
        "say": "Deep rumble, fast, a bit flat",
        "match": ["rumble", "like now", "like before", "cheap", "fast and flat", "robot"],
    },
    {
        "id": "natural",
        "provider": "kokoro",
        "say": "Natural documentary narrator",
        "match": [
            "natural",
            "clean",
            "person reading",
            "like a person reading",
            "real narrator",
            "like a real narrator",
        ],
    },
    {
        "id": "emotional",
        "provider": "chatterbox",
        "say": "More emotional, like someone telling you the story",
        "match": [
            "emotional",
            "more human",
            "human",
            "not flat",
            "not robotic",
            "not monotone",
            "someone telling",
            "telling you the story",
            "more life",
            "alive",
        ],
    },
    {
        "id": "acted",
        "provider": "orpheus",
        "say": "Fully acted, with breath and feeling",
        "match": ["acted", "dramatic", "breath", "feeling", "sighs", "performance", "fully acted"],
    },
]

_YOU_PICK = {
    "whatever",
    "you pick",
    "your pick",
    "default",
    "surprise me",
    "i don't care",
    "i dont care",
    "idk",
    "up to you",
    "you decide",
    "best",
    "the good one",
    "better",
}

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


def venv_python(env: Path) -> Path | None:
    for rel in ("bin/python", "Scripts/python.exe"):
        path = env / rel
        if path.exists():
            return path
    return None


def piper_python() -> Path | None:
    return venv_python(PIPER_ENV)


def tts_python() -> Path | None:
    return venv_python(TTS_ENV)


def expected_venv_python(env: Path) -> Path:
    found = venv_python(env)
    if found:
        return found
    if sys.platform == "win32":
        return env / "Scripts" / "python.exe"
    return env / "bin" / "python"


def python_for_provider(provider: str) -> Path:
    if provider in LOCAL_TORCH_PROVIDERS:
        return expected_venv_python(TTS_ENV)
    return piper_python() or Path(sys.executable)


def _can_import(module: str, python: Path | None = None) -> bool:
    if python is None:
        try:
            __import__(module)
            return True
        except Exception:
            return False
    try:
        proc = subprocess.run(
            [str(python), "-c", f"import {module}"],
            capture_output=True,
            timeout=45,
        )
        return proc.returncode == 0
    except Exception:
        return False


def provider_available(name: str) -> bool:
    if name == "piper":
        voices = any(PIPER_VOICES.glob("*.onnx")) if PIPER_VOICES.is_dir() else False
        py = piper_python()
        return bool(voices or _can_import("piper") or (py and _can_import("piper", py)))
    if name == "kokoro":
        py = tts_python()
        return _can_import("kokoro") or bool(py and _can_import("kokoro", py))
    if name == "chatterbox":
        py = tts_python()
        return _can_import("chatterbox") or bool(py and _can_import("chatterbox", py))
    if name == "orpheus":
        py = tts_python()
        return _can_import("orpheus_tts") or bool(py and _can_import("orpheus_tts", py))
    if name in PAID_PROVIDERS:
        return True
    return False


def installed_local_providers() -> dict[str, bool]:
    return {
        "piper": provider_available("piper"),
        "kokoro": provider_available("kokoro"),
        "chatterbox": provider_available("chatterbox"),
        "orpheus": provider_available("orpheus"),
    }


def _contains_phrase(text: str, phrase: str) -> bool:
    if " " in phrase:
        return phrase in text
    return bool(re.search(rf"\b{re.escape(phrase)}\b", text))


def _default_option(options: list[dict]) -> dict | None:
    for opt in options:
        if opt["provider"] == DEFAULT_LOCAL_PROVIDER:
            return opt
    return options[0] if options else None


def available_voice_options() -> list[dict]:
    return [dict(opt) for opt in VOICE_INTENTS if provider_available(opt["provider"])]


def _score_intent(raw: str, pool: list[dict]) -> tuple[int, dict | None]:
    scored: list[tuple[int, dict]] = []
    for opt in pool:
        score = 0
        for phrase in opt["match"]:
            if phrase in {"flat", "robotic", "monotone"} and f"not {phrase}" in raw:
                continue
            if _contains_phrase(raw, phrase):
                score += max(3, len(phrase))
        say = str(opt["say"]).lower()
        if say and say in raw:
            score += len(say)
        if _contains_phrase(raw, opt["id"]):
            score += 6
        if _contains_phrase(raw, opt["provider"]):
            score += 20
        scored.append((score, opt))
    if not scored:
        return 0, None
    return max(scored, key=lambda item: item[0])


def resolve_voice_intent(text: str, options: list[dict] | None = None) -> dict:
    """Map a plain-English reply to a local provider. Never requires engine names."""
    raw = " ".join((text or "").lower().split())
    installed = available_voice_options()
    pool = options if options is not None else list(VOICE_INTENTS)
    fallback = _default_option(pool) or _default_option(installed)
    if not raw or raw in _YOU_PICK:
        if fallback is None:
            return {
                "ok": False,
                "provider": None,
                "id": None,
                "installed": False,
                "setup": f"bash {ROOT / 'scripts' / 'setup_local_tts.sh'}",
            }
        ready = provider_available(fallback["provider"])
        return {
            "ok": True,
            "provider": fallback["provider"],
            "id": fallback["id"],
            "installed": ready,
            "python": str(python_for_provider(fallback["provider"])),
            "setup": "" if ready else f"bash {ROOT / 'scripts' / 'setup_local_tts.sh'}",
        }

    best_score, best = _score_intent(raw, pool)
    if (not best or best_score <= 0) and options is None:
        best_score, best = _score_intent(raw, list(VOICE_INTENTS))
    if not best or best_score <= 0:
        return {
            "ok": False,
            "provider": None,
            "id": None,
            "installed": False,
            "setup": f"bash {ROOT / 'scripts' / 'setup_local_tts.sh'}",
        }
    ready = provider_available(best["provider"])
    return {
        "ok": True,
        "provider": best["provider"],
        "id": best["id"],
        "installed": ready,
        "python": str(python_for_provider(best["provider"])),
        "setup": "" if ready else f"bash {ROOT / 'scripts' / 'setup_local_tts.sh'}",
    }


def voice_menu() -> dict:
    options = []
    for opt in VOICE_INTENTS:
        item = dict(opt)
        item["available"] = provider_available(opt["provider"])
        options.append(item)
    default = DEFAULT_LOCAL_PROVIDER
    py_map = {
        "piper": str(python_for_provider("piper")),
        "kokoro": str(python_for_provider("kokoro")),
        "chatterbox": str(python_for_provider("chatterbox")),
        "orpheus": str(python_for_provider("orpheus")),
        "elevenlabs": str(python_for_provider("elevenlabs")),
        "heygen": str(python_for_provider("heygen")),
    }
    return {
        "question": "How should the narrator sound?",
        "default": default,
        "options": options,
        "installed": installed_local_providers(),
        "python": py_map,
        "narrator_wav": str(NARRATOR_WAV) if NARRATOR_WAV.exists() else "",
        "setup": f"bash {ROOT / 'scripts' / 'setup_local_tts.sh'}",
        "hint": (
            "Ask using only the say lines. Never name engines unless the user "
            "asks what you used. If the reply is unclear, ask one follow-up "
            "in the same plain language."
        ),
    }


def print_voice_menu() -> None:
    print(json.dumps(voice_menu(), indent=2))


def print_resolve_intent(text: str) -> None:
    print(json.dumps(resolve_voice_intent(text), indent=2))


def parse_topic(raw: str) -> dict:
    text = " ".join(raw.strip().split())
    tokens = re.split(r"\s+-\s+", text)
    provider = DEFAULT_LOCAL_PROVIDER
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
    if provider == "kokoro" and not voice:
        voice = DEFAULT_KOKORO_VOICE
    if provider == "orpheus" and not voice:
        voice = DEFAULT_ORPHEUS_VOICE
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
