#!/usr/bin/env python3
"""Generate documentary voiceover audio with Piper (local) or ElevenLabs.

Resume is stored in SQLite next to the audio files. A failed run continues
from the first unfinished scene.

Topic flags (no code changes needed):

  jeffrey dahmer
  jeffrey dahmer - piper
  jeffrey dahmer - elevenlabs
  jeffrey dahmer - elevenlabs - adam
  jeffrey dahmer - elevenlabs - daniel
  jeffrey dahmer - elevenlabs - deep male

ElevenLabs key: export ELEVENLABS_API_KEY or put it in .env / tools/.env
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import wave
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
VOICES_DIR = ROOT / "tools" / "piper-voices"
DEFAULT_PIPER = "en_US-ryan-high"
FALLBACK_PIPER = "en_US-lessac-medium"
ELEVEN_PCM_RATE = 22050

SCENE_RE = re.compile(r"^Scene\s+(\d+)\s*$", re.IGNORECASE)
PAUSE_RE = re.compile(r"^\((long\s+pause|pause)\)\s*$", re.IGNORECASE)
TOTAL_RE = re.compile(r"^Total Scenes:\s*\d+\s*$", re.IGNORECASE)
VOICE_ID_RE = re.compile(r"^[A-Za-z0-9]{16,28}$")

PROVIDERS = {
    "elevenlabs": "elevenlabs",
    "11labs": "elevenlabs",
    "eleven": "elevenlabs",
    "piper": "piper",
    "local": "piper",
}

# Hands-off aliases. User types these after "- elevenlabs -"
ELEVEN_ALIASES = {
    "adam": "pNInz6obpgDQGcFmaJgB",
    "default": "pNInz6obpgDQGcFmaJgB",
    "deep": "pNInz6obpgDQGcFmaJgB",
    "deep male": "pNInz6obpgDQGcFmaJgB",
    "documentary": "pNInz6obpgDQGcFmaJgB",
    "narrator": "pNInz6obpgDQGcFmaJgB",
    "rumble": "pNInz6obpgDQGcFmaJgB",
    "youtube": "pNInz6obpgDQGcFmaJgB",
    "daniel": "onwK4e9ZLuTAKqWW03F9",
    "news": "onwK4e9ZLuTAKqWW03F9",
    "british": "onwK4e9ZLuTAKqWW03F9",
    "chris": "iP95p4xoKVk53GoZ742B",
    "antoni": "ErXwobaYiN019PkySvjV",
    "warm": "ErXwobaYiN019PkySvjV",
    "josh": "TxGEqnHWrfWFTfGW9XjX",
    "bill": "pqHfZKP75CvOlQylNhV4",
    "gravel": "pqHfZKP75CvOlQylNhV4",
    "clyde": "2EiwWnXFnvU5JabPnv8n",
    "drew": "29vD33N1CtxCmqQRPOHJ",
    "brian": "nPczCjzI2devNBz1zQrb",
    "george": "JBFqnCBsd6RMkjVDRZzb",
    "rachel": "21m00Tcm4TlvDq8ikWAM",
    "sarah": "EXAVITQu4vr4xnSDxMaL",
}

DEFAULT_ELEVEN_VOICE = "adam"


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
    return {
        "topic": topic,
        "slug": slugify(topic),
        "provider": provider,
        "voice": voice,
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


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
            audio_path TEXT,
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
    provider: str,
    voice: str,
    settings: dict,
) -> int:
    settings_json = json.dumps(settings, sort_keys=True)
    row = conn.execute(
        """
        SELECT id FROM job
        WHERE input_path = ? AND input_hash = ? AND provider = ?
          AND voice = ? AND settings_json = ?
        ORDER BY id DESC LIMIT 1
        """,
        (str(input_path), input_hash, provider, voice, settings_json),
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
        VALUES (?, ?, ?, ?, ?, 'running', ?, ?)
        """,
        (str(input_path), input_hash, provider, voice, settings_json, now_iso(), now_iso()),
    )
    conn.commit()
    return int(cur.lastrowid)


def scene_is_done(conn: sqlite3.Connection, job_id: int, number: int, thash: str, wav: Path) -> bool:
    if not wav.exists() or wav.stat().st_size < 1000:
        return False
    row = conn.execute(
        "SELECT text_hash, status FROM scene WHERE job_id = ? AND scene_number = ?",
        (job_id, number),
    ).fetchone()
    return bool(row and row["status"] == "done" and row["text_hash"] == thash)


def mark_scene(
    conn: sqlite3.Connection,
    job_id: int,
    number: int,
    thash: str,
    status: str,
    audio_path: str | None,
    error: str | None,
    duration: float | None,
) -> None:
    conn.execute(
        """
        INSERT INTO scene (job_id, scene_number, text_hash, status, audio_path, error, duration_sec)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_id, scene_number) DO UPDATE SET
            text_hash = excluded.text_hash,
            status = excluded.status,
            audio_path = excluded.audio_path,
            error = excluded.error,
            duration_sec = excluded.duration_sec
        """,
        (job_id, number, thash, status, audio_path, error, duration),
    )
    conn.execute("UPDATE job SET updated_at = ? WHERE id = ?", (now_iso(), job_id))
    conn.commit()


def resample(audio: np.ndarray, new_len: int) -> np.ndarray:
    if new_len <= 0 or len(audio) == 0 or new_len == len(audio):
        return audio
    old_idx = np.linspace(0.0, 1.0, num=len(audio), endpoint=False)
    new_idx = np.linspace(0.0, 1.0, num=new_len, endpoint=False)
    return np.interp(new_idx, old_idx, audio).astype(np.float32)


def pitch_shift(audio: np.ndarray, semitones: float) -> np.ndarray:
    if abs(semitones) < 0.01:
        return audio
    factor = 2 ** (semitones / 12.0)
    stretched = resample(audio, max(1, int(round(len(audio) / factor))))
    return resample(stretched, len(audio))


def add_warmth(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    kernel_n = max(3, int(sample_rate / 220))
    kernel = np.ones(kernel_n, dtype=np.float32) / kernel_n
    low = np.convolve(audio, kernel, mode="same")
    mixed = audio * 0.82 + low * 0.28
    peak = float(np.max(np.abs(mixed)))
    if peak > 0.98:
        mixed = mixed * (0.98 / peak)
    return mixed.astype(np.float32)


def silence(seconds: float, sample_rate: int) -> np.ndarray:
    return np.zeros(max(0, int(round(seconds * sample_rate))), dtype=np.float32)


def write_wav(path: Path, audio: np.ndarray, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(audio, -1.0, 1.0) * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wav:
        rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())
        width = wav.getsampwidth()
    if width == 2:
        pcm = np.frombuffer(frames, dtype=np.int16)
        return pcm.astype(np.float32) / 32767.0, rate
    raise SystemExit(f"Unsupported WAV width in {path}")


def resolve_piper_voice(name: str | None) -> Path:
    chosen = name or (
        DEFAULT_PIPER if (VOICES_DIR / f"{DEFAULT_PIPER}.onnx").exists() else FALLBACK_PIPER
    )
    path = Path(chosen)
    if not path.suffix:
        path = VOICES_DIR / f"{chosen}.onnx"
    elif not path.is_absolute():
        path = VOICES_DIR / path.name
    if not path.exists():
        raise SystemExit(f"Piper voice not found: {path}")
    return path


def elevenlabs_key() -> str:
    load_dotenv()
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "ElevenLabs requested but ELEVENLABS_API_KEY is missing.\n"
            "Add it with: export ELEVENLABS_API_KEY=...   or put it in .env"
        )
    return key


def http_json(url: str, key: str, data: dict | None = None) -> dict:
    body = None if data is None else json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="GET" if data is None else "POST")
    req.add_header("xi-api-key", key)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def resolve_eleven_voice(hint: str, key: str) -> tuple[str, str]:
    raw = (hint or DEFAULT_ELEVEN_VOICE).strip()
    if VOICE_ID_RE.match(raw):
        return raw, raw
    alias = ELEVEN_ALIASES.get(raw.lower())
    if alias:
        return alias, raw.lower()
    try:
        payload = http_json("https://api.elevenlabs.io/v1/voices", key)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Could not list ElevenLabs voices: {exc}") from exc
    voices = payload.get("voices") or []
    needle = raw.lower()
    for voice in voices:
        name = str(voice.get("name") or "")
        if name.lower() == needle:
            return str(voice["voice_id"]), name
    for voice in voices:
        name = str(voice.get("name") or "")
        labels = " ".join(str(v) for v in (voice.get("labels") or {}).values())
        blob = f"{name} {labels}".lower()
        if needle in blob:
            return str(voice["voice_id"]), name
    known = ", ".join(sorted({k for k in ELEVEN_ALIASES if " " not in k}))
    raise SystemExit(
        f"ElevenLabs voice '{raw}' not found. Use a name, a description, or an ID.\n"
        f"Built-in aliases: {known}"
    )


def prepare_cuda_dll_path() -> list[Path]:
    """Expose pip-installed NVIDIA CUDA/cuDNN DLLs to onnxruntime on Windows."""
    site = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
    candidates = [
        site / "cu13" / "bin" / "x86_64",
        site / "cudnn" / "bin",
        site / "cu12" / "bin",
        site / "cublas" / "bin",
        site / "cuda_runtime" / "bin",
    ]
    found = [p for p in candidates if p.is_dir()]
    if not found:
        return []
    path_parts = os.environ.get("PATH", "").split(os.pathsep)
    prepend: list[str] = []
    for folder in found:
        text = str(folder)
        if text not in path_parts:
            prepend.append(text)
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(text)
            except OSError:
                pass
    if prepend:
        os.environ["PATH"] = os.pathsep.join(prepend + path_parts)
    return found


def cuda_available() -> bool:
    prepare_cuda_dll_path()
    try:
        import onnxruntime as ort

        return "CUDAExecutionProvider" in ort.get_available_providers()
    except Exception:
        return False


def load_piper_voice(model_path: Path):
    """Load Piper with CUDA when possible; fall back to CPU."""
    from piper import PiperVoice

    if cuda_available():
        try:
            voice = PiperVoice.load(str(model_path), use_cuda=True)
            providers = list(getattr(voice.session, "get_providers", lambda: [])())
            if any("CUDA" in str(p) for p in providers):
                return voice, "cuda"
            print("CUDA provider listed but session stayed on CPU; using CPU")
        except Exception as exc:
            print(f"CUDA load failed ({exc}); falling back to CPU")
    return PiperVoice.load(str(model_path), use_cuda=False), "cpu"


def synthesize_piper(text: str, voice, syn_config) -> tuple[np.ndarray, int]:
    chunks: list[np.ndarray] = []
    sample_rate = 22050
    for chunk in voice.synthesize(text, syn_config=syn_config):
        sample_rate = chunk.sample_rate
        chunks.append(chunk.audio_float_array)
    if not chunks:
        return np.zeros(0, dtype=np.float32), sample_rate
    return np.concatenate(chunks), sample_rate


def synthesize_eleven(text: str, voice_id: str, key: str) -> tuple[np.ndarray, int]:
    url = (
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        f"?output_format=pcm_22050"
    )
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.58,
            "similarity_boost": 0.78,
            "style": 0.12,
            "use_speaker_boost": True,
        },
    }
    last_error: Exception | None = None
    for attempt in range(4):
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
        )
        req.add_header("xi-api-key", key)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/octet-stream")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read()
            pcm = np.frombuffer(raw, dtype="<i2")
            return pcm.astype(np.float32) / 32767.0, ELEVEN_PCM_RATE
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 429:
                time.sleep(2 ** attempt)
                continue
            detail = exc.read().decode("utf-8", errors="replace")
            raise SystemExit(f"ElevenLabs error {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            last_error = exc
            time.sleep(2 ** attempt)
    raise SystemExit(f"ElevenLabs failed after retries: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate documentary voiceover audio")
    parser.add_argument("input", nargs="?", help="03-voiceover.md or a plain script")
    parser.add_argument("--parse-topic", help="Print topic/provider/voice JSON and exit")
    parser.add_argument("--from-topic", help="Raw user topic, e.g. 'jeffrey dahmer - elevenlabs - adam'")
    parser.add_argument("--output-dir", help="Directory for WAV files")
    parser.add_argument("--provider", choices=["piper", "elevenlabs"])
    parser.add_argument("--voice", default=None, help="Piper model, ElevenLabs name, alias, or voice ID")
    parser.add_argument("--semitones", type=float, default=-3.5)
    parser.add_argument("--length-scale", type=float, default=1.15)
    parser.add_argument("--pause", type=float, default=0.45)
    parser.add_argument("--long-pause", type=float, default=1.15)
    parser.add_argument("--no-deep", action="store_true")
    parser.add_argument("--force", action="store_true", help="Regenerate scenes even if SQLite says done")
    args = parser.parse_args()

    if args.parse_topic is not None:
        print(json.dumps(parse_topic(args.parse_topic), indent=2))
        return 0

    if not args.input:
        parser.error("Pass a voiceover file")

    topic_meta = parse_topic(args.from_topic) if args.from_topic else None
    provider = args.provider or (topic_meta["provider"] if topic_meta else "piper")
    voice_hint = args.voice or (topic_meta["voice"] if topic_meta else "")

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        raise SystemExit(f"Input not found: {input_path}")

    out_dir = Path(args.output_dir) if args.output_dir else input_path.parent / "audio"
    out_dir.mkdir(parents=True, exist_ok=True)

    source_text = input_path.read_text(encoding="utf-8")
    scenes = parse_voiceover(source_text)
    settings = {
        "semitones": args.semitones,
        "length_scale": args.length_scale,
        "no_deep": args.no_deep,
        "pause": args.pause,
        "long_pause": args.long_pause,
    }

    piper_voice = None
    syn_config = None
    eleven_key = ""
    resolved_voice = voice_hint

    if provider == "piper":
        try:
            from piper import PiperVoice
            from piper.config import SynthesisConfig
        except ImportError:
            raise SystemExit(
                "Piper is not on this Python. Run with:\n"
                f"  {ROOT / 'tools' / 'piper-env' / 'Scripts' / 'python.exe'} scripts/generate_voiceover.py ..."
            )
        model_path = resolve_piper_voice(voice_hint or None)
        resolved_voice = model_path.stem
        piper_voice, device = load_piper_voice(model_path)
        print(f"Provider piper  voice {model_path.name}  device {device}")
        syn_config = SynthesisConfig(length_scale=args.length_scale, volume=0.95)
    else:
        eleven_key = elevenlabs_key()
        voice_id, label = resolve_eleven_voice(voice_hint, eleven_key)
        resolved_voice = voice_id
        print(f"Provider elevenlabs  voice {label} ({voice_id})")

    conn = connect_db(out_dir / "progress.sqlite")
    job_id = get_or_create_job(
        conn,
        input_path,
        text_hash(source_text),
        provider,
        resolved_voice,
        settings,
    )
    print(f"Job {job_id}  {len(scenes)} scenes  resume db {out_dir / 'progress.sqlite'}")

    mix: list[np.ndarray] = []
    manifest: list[dict] = []
    sample_rate = ELEVEN_PCM_RATE
    generated = 0
    skipped = 0
    failed = 0

    for scene in scenes:
        number = scene["number"]
        thash = text_hash(scene["text"])
        scene_name = f"scene-{number:03d}.wav"
        wav_path = out_dir / scene_name
        pause_s = args.long_pause if scene["pause"] == "long" else args.pause

        if not args.force and scene_is_done(conn, job_id, number, thash, wav_path):
            audio, sample_rate = read_wav(wav_path)
            skipped += 1
            print(f"  skip  {number:03d}  already done")
        else:
            try:
                if provider == "piper":
                    audio, sample_rate = synthesize_piper(scene["text"], piper_voice, syn_config)
                    if not args.no_deep:
                        audio = pitch_shift(audio, args.semitones)
                        audio = add_warmth(audio, sample_rate)
                else:
                    audio, sample_rate = synthesize_eleven(scene["text"], resolved_voice, eleven_key)
                    time.sleep(0.15)
                write_wav(wav_path, audio, sample_rate)
                duration = len(audio) / sample_rate if sample_rate else 0
                mark_scene(conn, job_id, number, thash, "done", str(wav_path), None, duration)
                generated += 1
                print(f"  scene {number:03d}  {duration:5.1f}s  {scene['text'][:72]}")
            except SystemExit:
                raise
            except Exception as exc:
                failed += 1
                mark_scene(conn, job_id, number, thash, "failed", None, str(exc), None)
                print(f"  FAIL  {number:03d}  {exc}")
                continue

        duration = len(audio) / sample_rate if sample_rate else 0
        mix.append(audio)
        mix.append(silence(pause_s, sample_rate))
        manifest.append(
            {
                "scene": number,
                "file": scene_name,
                "pause": scene["pause"],
                "duration_sec": round(duration, 3),
                "words": len(scene["text"].split()),
                "text": scene["text"],
            }
        )

    if failed:
        conn.execute(
            "UPDATE job SET status = ?, updated_at = ? WHERE id = ?",
            ("failed", now_iso(), job_id),
        )
        conn.commit()
        print(f"Stopped with {failed} failed scene(s). Re-run the same command to resume.")
        return 1

    full = np.concatenate(mix) if mix else np.zeros(0, dtype=np.float32)
    write_wav(out_dir / "full-voiceover.wav", full, sample_rate)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    conn.execute(
        "UPDATE job SET status = ?, updated_at = ? WHERE id = ?",
        ("done", now_iso(), job_id),
    )
    conn.commit()
    conn.close()

    total = len(full) / sample_rate if sample_rate else 0
    print(f"Wrote {out_dir / 'full-voiceover.wav'}")
    print(
        f"Total runtime: {total/60:.1f} min ({total:.0f}s)  "
        f"generated {generated}  skipped {skipped}  scenes {len(scenes)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
