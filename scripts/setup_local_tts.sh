#!/usr/bin/env bash
# Install Kokoro, Chatterbox, and Orpheus in tools/tts-env.
# Does not touch tools/piper-env.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_DIR="$ROOT/tools/tts-env"
VOICE_DIR="$ROOT/tools/voices"

pick_python() {
  if [[ -n "${PYTHON:-}" ]]; then
    echo "$PYTHON"
    return
  fi
  for candidate in python3.12 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      echo "$candidate"
      return
    fi
  done
  echo "Need Python 3.12. Install it, then rerun." >&2
  exit 1
}

PYTHON_BIN="$(pick_python)"
VERSION="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$VERSION" != "3.12" ]]; then
  echo "Warning: $PYTHON_BIN is Python $VERSION. 3.12 is recommended." >&2
fi

mkdir -p "$VOICE_DIR"
if [[ ! -d "$ENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$ENV_DIR"
fi

if [[ -x "$ENV_DIR/bin/python" ]]; then
  PY="$ENV_DIR/bin/python"
elif [[ -x "$ENV_DIR/Scripts/python.exe" ]]; then
  PY="$ENV_DIR/Scripts/python.exe"
else
  echo "Could not find the new venv python in $ENV_DIR" >&2
  exit 1
fi

PIP=("$PY" -m pip)
"${PIP[@]}" install --upgrade pip wheel

HAS_NVIDIA=0
if command -v nvidia-smi >/dev/null 2>&1; then
  HAS_NVIDIA=1
fi

if [[ "$HAS_NVIDIA" -eq 1 ]]; then
  echo "NVIDIA GPU detected. Installing PyTorch with CUDA 12.8 (Blackwell / 5080)."
  "${PIP[@]}" install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
else
  echo "No nvidia-smi. Installing default PyTorch (CPU or Apple Silicon)."
  "${PIP[@]}" install torch torchaudio
fi

"${PIP[@]}" install "kokoro>=0.9" "misaki[en]" soundfile numpy
"${PIP[@]}" install chatterbox-tts

if [[ "$HAS_NVIDIA" -eq 1 ]]; then
  # chatterbox-tts may pin an older torch; put the 12.8 wheel back.
  "${PIP[@]}" install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
fi

if [[ "$HAS_NVIDIA" -eq 1 ]]; then
  if "${PIP[@]}" install orpheus-speech; then
    echo "Orpheus installed."
  else
    echo "Orpheus skipped (orpheus-speech / vLLM failed). The other local voices still work." >&2
  fi
else
  echo "Orpheus skipped on this machine (needs CUDA + vLLM). Install on the 5080 box to enable it."
fi

echo
echo "Local voices are in $ENV_DIR"
echo "Optional clone clip: drop a dry 8–15s WAV at $VOICE_DIR/narrator.wav"
echo "Check what the AI can offer:"
echo "  $PY $ROOT/scripts/generate_voiceover.py --voice-menu"
