# Local voice install

This repo needs two Python environments:

| Folder | What it is | Used for |
|---|---|---|
| `tools/piper-env` | Small, already documented in the README | Deep rumble voice, paid APIs, topic parse |
| `tools/tts-env` | PyTorch voices | Natural, emotional, and fully-acted local narration |

You never type those engine names in chat. After install, you just say how it should sound.

**Use Python 3.12.** 3.14 breaks Piper wheels. 3.13 is untested.

---

## Which machine

| Machine | What works well | What is weak |
|---|---|---|
| **Windows + Blackwell** (RTX 5070 / 5080 / 5090) | Natural + emotional voices, fast | Fully-acted often fails (needs vLLM, which is a Linux stack) |
| **M-series Mac** (M1–M4) | Rumble + natural; emotional works, slower | Fully-acted is skipped on purpose |

A 5080 is more than enough. Blackwell cards need a **CUDA 12.8 (or 12.9) PyTorch wheel**. A default `pip install torch` will crash with `sm_120 is not compatible`.

---

## Windows + Blackwell (RTX 50-series)

### 1. Driver and Python

1. Install the latest **Game Ready or Studio** driver for your 50-series card from NVIDIA.
2. Reboot.
3. Install **[Python 3.12](https://www.python.org/downloads/)** (Windows installer).
   - Check **Add python.exe to PATH**.
   - Do not use the Microsoft Store Python 3.13/3.14 build.
4. Install **[Git for Windows](https://git-scm.com/download/win)** so you have Git Bash.
5. Optional: [GitHub CLI](https://cli.github.com/) (`winget install GitHub.cli`) so the pipeline gate can sign in.

Confirm the GPU is visible:

```powershell
nvidia-smi
python --version
```

You want a 50-series name in `nvidia-smi` and `Python 3.12.x`.

You do **not** need a full CUDA Toolkit install. The PyTorch `cu128` wheel brings the libraries it needs.

### 2. Clone and rumble voice (Piper)

In **Git Bash** (not cmd, unless you translate the paths):

```bash
cd /c/Users/YOU/path/to/youtube

python -m venv tools/piper-env
tools/piper-env/Scripts/python.exe -m pip install --upgrade pip
tools/piper-env/Scripts/python.exe -m pip install piper-tts numpy

mkdir -p tools/piper-voices
curl -L -o tools/piper-voices/en_US-ryan-high.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx"
curl -L -o tools/piper-voices/en_US-ryan-high.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx.json"
curl -L -o tools/piper-voices/en_US-lessac-medium.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
curl -L -o tools/piper-voices/en_US-lessac-medium.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
```

PowerShell equivalent for the venv:

```powershell
cd C:\Users\YOU\path\to\youtube
py -3.12 -m venv tools\piper-env
tools\piper-env\Scripts\python.exe -m pip install --upgrade pip
tools\piper-env\Scripts\python.exe -m pip install piper-tts numpy
```

### 3. Natural / emotional voices

Still in the repo root, **Git Bash**:

```bash
bash scripts/setup_local_tts.sh
```

Or PowerShell, by hand (this is what the script does on NVIDIA):

```powershell
py -3.12 -m venv tools\tts-env
tools\tts-env\Scripts\python.exe -m pip install --upgrade pip wheel
tools\tts-env\Scripts\python.exe -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
tools\tts-env\Scripts\python.exe -m pip install "kokoro>=0.9" "misaki[en]" soundfile numpy
tools\tts-env\Scripts\python.exe -m pip install chatterbox-tts
# chatterbox-tts pins torch==2.6.0 (no sm_120). Force Blackwell wheels back —
# a plain reinstall is a no-op because pip thinks 2.6.0 already satisfies torch.
tools\tts-env\Scripts\python.exe -m pip install --force-reinstall torch torchaudio --index-url https://download.pytorch.org/whl/cu128
```

If your default `python` is 3.14, always use `py -3.12` for both venvs (as above). Do not create them with store Python.

The fully-acted install (`orpheus-speech`) is attempted by the bash script. On native Windows it usually **fails**. That is expected. Natural and emotional voices still work. If you truly need the fully-acted option, use WSL2 Ubuntu on the same 5080 (same `cu128` steps, then `pip install orpheus-speech`).

### 4. Prove the 5080 is actually in use

```powershell
tools\tts-env\Scripts\python.exe -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no cuda')"
```

Good: `2.11.x+cu128` (or newer), `True`, `NVIDIA GeForce RTX 5080`.

Bad: `False`, `2.6.0` without `+cu128`, or a crash mentioning `sm_120` / `not compatible`. Then **only** this (must use `--force-reinstall`), do not `pip install torch` from PyPI:

```powershell
tools\tts-env\Scripts\python.exe -m pip install --force-reinstall torch torchaudio --index-url https://download.pytorch.org/whl/cu128
```

If `cu128` is still old, try `cu129` at `https://download.pytorch.org/whl/cu129`.

### 5. What the AI can offer

```powershell
tools\piper-env\Scripts\python.exe scripts\generate_voiceover.py --voice-menu
```

`installed.kokoro` and `installed.chatterbox` should be `true` after a successful `tts-env` install.

### 6. Windows notes

- Run generation with `tools\tts-env\Scripts\python.exe` for natural/emotional voices, and `tools\piper-env\Scripts\python.exe` for rumble and paid APIs.
- First emotional generate downloads model weights from Hugging Face. Let it finish.
- Optional clone clip: `tools\voices\narrator.wav` (dry, 8–15 seconds, no music).
- `ffmpeg` is only required for HeyGen MP3 decode. `winget install Gyan.FFmpeg` if you use that paid path.

---

## M-series Mac (M1, M2, M3, M4)

### 1. Homebrew tools

```bash
xcode-select --install
brew install python@3.12 git gh ffmpeg
python3.12 --version
```

Sign GitHub in (`gh auth login`) before you run the documentary skill.

### 2. Rumble voice (Piper)

```bash
cd /path/to/youtube

python3.12 -m venv tools/piper-env
source tools/piper-env/bin/activate
pip install --upgrade pip
pip install piper-tts numpy
deactivate

mkdir -p tools/piper-voices
curl -L -o tools/piper-voices/en_US-ryan-high.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx"
curl -L -o tools/piper-voices/en_US-ryan-high.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx.json"
curl -L -o tools/piper-voices/en_US-lessac-medium.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
curl -L -o tools/piper-voices/en_US-lessac-medium.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
```

Smoke test:

```bash
source tools/piper-env/bin/activate
echo "This is a test of the documentary voiceover." | \
  piper --model tools/piper-voices/en_US-ryan-high.onnx \
        --output_file /tmp/piper-test.wav
afplay /tmp/piper-test.wav
deactivate
```

### 3. Natural / emotional voices

```bash
bash scripts/setup_local_tts.sh
```

There is no `nvidia-smi` on a Mac, so the script installs the default PyTorch wheel (Metal / MPS). It **skips** the fully-acted voice. That is expected.

Check MPS:

```bash
tools/tts-env/bin/python -c "import torch; print(torch.__version__); print(torch.backends.mps.is_available())"
```

You want `True` on any M-series Mac.

Then:

```bash
tools/piper-env/bin/python scripts/generate_voiceover.py --voice-menu
```

### 4. Mac notes

- Use `tools/tts-env/bin/python` for natural/emotional, `tools/piper-env/bin/python` for rumble and paid APIs.
- Emotional voice on MPS is fine for a 12–18 minute documentary. It is just slower than a 5080.
- If Chatterbox refuses MPS, the script falls back to CPU. Still works, slower.
- Optional clone clip: `tools/voices/narrator.wav`.
- Do not install the CUDA `cu128` wheel on a Mac.

---

## After install (both machines)

1. Open this folder in Cursor.
2. Type only the story (`jeffrey dahmer`).
3. When asked how it should sound, answer in plain English.

The AI maps that to the right `--provider`. You do not type engine names.

If the richer voices are not installed yet, the AI runs `bash scripts/setup_local_tts.sh` (or tells you to). On Windows, run that from **Git Bash**, or use the PowerShell block above.

---

## Common failures

| Symptom | Fix |
|---|---|
| `sm_120 is not compatible` / CUDA capability error | Force-reinstall torch from `cu128` or `cu129` (`--force-reinstall`). Never use the default PyPI torch on a 50-series card. |
| After chatterbox, torch shows `2.6.0` not `+cu128` | Expected. Run `pip install --force-reinstall torch torchaudio --index-url https://download.pytorch.org/whl/cu128` in `tts-env`. |
| `torch.cuda.is_available()` is `False` on Windows | Driver too old, or you installed a CPU/Mac wheel into `tts-env`. Force-reinstall `cu128`. |
| `chatterbox` / `kokoro` import fails | You ran the voiceover script with `piper-env`. Use `tools/tts-env/.../python`. |
| Piper `ModuleNotFoundError` | You ran it with `tts-env`. Use `tools/piper-env/.../python`. |
| Fully-acted not offered / install failed | Expected on Mac and on native Windows. Use a 5080 under WSL2/Linux if you need it. |
| Python 3.14 / store Python | Recreate both venvs with 3.12. |
| Hugging Face download hangs | First model pull is large. Retry the same generate command; SQLite resume skips finished scenes. |
| GitHub gate blocks the skill | `gh auth login` or SSH, then `bash scripts/require_github.sh`. |

---

## Disk

Plan a few gigabytes for `tools/tts-env` plus first-run model caches (Hugging Face home directory). Piper voices are small. Audio WAVs under `output/` stay local and are gitignored.
