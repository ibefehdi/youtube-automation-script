# Faceless Documentary Pipeline

Give this project **one topic**. It turns that topic into a full YouTube documentary package:

1. Deep research dossier  
2. 15,000–18,000 character narration script  
3. Timed 10-second voiceover scenes  
4. Spoken audio (local or paid — you describe how it should sound)  
5. AI video prompts for every scene (and optional HeyGen clips if you say yes)

You do not edit code to pick a voice. Type the **story** in chat. After the scenes are written, the AI asks how the narrator should sound in plain English. If `ELEVENLABS_API_KEY` or `HEYGEN_API_KEY` is set, it still asks **yes/no** before any paid script.

**You need a GitHub account signed in on the CLI.** The skill checks this first and will not generate anything until `gh auth login` or SSH to GitHub succeeds.

```
the silk road - dark web
jeffrey dahmer
```

---

## What you get

For a topic like `the silk road - dark web`, files land in `output/the-silk-road-dark-web/`:

```
output/<slug>/
  01-research.md          Full case file (timeline, people, sources)
  02-script.md            Ready-to-narrate documentary script
  03-voiceover.md         Same words, split into ~10-second scenes
  04-video-prompts.md     One visual prompt per scene
  audio/
    scene-001.wav
    scene-002.wav
    ...
    full-voiceover.wav    All scenes + pauses, one mix
    manifest.json         Scene list, durations, text
    progress.sqlite       Resume database
  video/                  HeyGen clips, only if you said yes
    scene-001.mp4
    progress.sqlite
```

A finished 15k–18k character script is roughly **12–18 minutes** of narration and about **70–120 scenes**.

---

## How to run it

### In Cursor

Open this folder, then type a topic in chat:

```
the silk road - dark web
```

or name the skill:

```
@youtube-documentary-pipeline jeffrey dahmer
```

### In Claude Code

```
/youtube-documentary-pipeline the silk road - dark web
```

The agent **first checks that GitHub is signed in**. If not, it stops and asks you to log in. After the voiceover script is written, it asks how the narrator should sound, and **yes/no** for any paid key that is set. It only runs those scripts after you answer.

### Audio only (if the markdown already exists)

The AI normally picks the engine from your chat reply. These commands are for reruns:

```bash
cd /path/to/this/repo

# Local (after you described the sound)
tools/tts-env/bin/python scripts/generate_voiceover.py \
  output/the-silk-road-dark-web/03-voiceover.md --provider chatterbox

# Rumble / fast local
tools/piper-env/bin/python scripts/generate_voiceover.py \
  output/the-silk-road-dark-web/03-voiceover.md --provider piper

# ElevenLabs
tools/piper-env/bin/python scripts/generate_voiceover.py \
  output/the-silk-road-dark-web/03-voiceover.md --provider elevenlabs

# HeyGen voiceover
tools/piper-env/bin/python scripts/generate_voiceover.py \
  output/the-silk-road-dark-web/03-voiceover.md --provider heygen

# HeyGen video clips (after 04-video-prompts.md exists)
tools/piper-env/bin/python scripts/generate_video.py \
  output/the-silk-road-dark-web/04-video-prompts.md \
  --from-topic "the silk road - dark web"
```

Listen:

```bash
afplay output/the-silk-road-dark-web/audio/full-voiceover.wav
```

---

## Hard requirement: GitHub on the CLI

The pipeline **will not start** until this computer is signed in to GitHub. That is checked first with `scripts/require_github.sh`.

If the check fails, the agent **stops**. It will not write research, scripts, or audio. Sign in, then send the same topic again.

### Server-side: GitHub rejects removing the gate

Local checks are not enough — someone could delete `require_github.sh` and push. After the workflow is on `main`, the **repo owner** turns on push rejection once:

```bash
gh auth login
bash scripts/setup_github_gate_protection.sh
```

That installs GitHub rulesets so pushes that **change or delete** the gate files (`scripts/require_github.sh`, both pipeline `SKILL.md` files, and the protect workflow) are **rejected by GitHub**. Normal pipeline commits are unaffected. Admins can still bypass to update the gate on purpose. CI also fails if those files are missing or hollowed out.

```bash
# Easiest
brew install gh
gh auth login
gh auth status

# Or SSH
ssh-keygen -t ed25519 -C "you@email.com"
# GitHub → Settings → SSH and GPG keys → paste ~/.ssh/id_ed25519.pub
ssh -T git@github.com
```

Each person uses **their own** GitHub account. The repo owner invites them as a collaborator (Write). Accept the invite before running the skill.

Manual check:

```bash
bash scripts/require_github.sh
```

Exit code 0 means generation is allowed.

---

## Topic syntax

Type the story. Dashes in the case name are fine (`the silk road - dark web`). You do **not** add a voice flag.

| You type | Story researched |
|---|---|
| `the silk road - dark web` | Silk Road |
| `jeffrey dahmer` | Jeffrey Dahmer |

The folder name is the **story slug**: `output/jeffrey-dahmer/`.

After `03-voiceover.md`, the AI asks how it should sound. Reply in normal language:

> How should this sound?
> - Deep rumble, fast, a bit flat
> - Natural documentary narrator
> - More emotional, like someone telling you the story
> - Fully acted, with breath and feeling

“More human” or “not robotic” is enough. You can later say “redo it, more human” and it regenerates.

Paid keys still get a yes/no. Local is the fallback when you say no, after the sound question.

---

## Voices

You pick by **sound**, in chat. First time on a machine, follow **[INSTALL.md](INSTALL.md)** (Windows Blackwell / 5080, or M-series Mac), or:

```bash
bash scripts/setup_local_tts.sh
```

That creates `tools/tts-env` (does not touch Piper). Optional: drop an 8–15s dry WAV at `tools/voices/narrator.wav` to steer the more emotional local voice.

### ElevenLabs (paid)

```bash
echo 'ELEVENLABS_API_KEY=your_key_here' >> .env
```

The file can also live at `tools/.env`. Do not commit the key. Default paid voice is **Adam**. Having the key does **not** start a run.

### HeyGen (paid, voiceover and optional video)

```bash
echo 'HEYGEN_API_KEY=your_key_here' >> .env
```

The AI asks two yes/no questions: HeyGen voiceover, and HeyGen video. Video clips come from `04-video-prompts.md` via Video Agent (landscape, exact narration, no captions). Each clip can take several minutes and uses credits.

What the AI picked (only if you ask): rumble → Piper, natural → Kokoro, emotional → Chatterbox, fully acted → Orpheus. Paid yes → ElevenLabs or HeyGen.

---

## Resume (if audio fails)

Progress is stored in `output/<slug>/audio/progress.sqlite`.

If generation dies on scene 40:

1. Do **not** delete the `audio/` folder  
2. Run the **same** command again  
3. Finished scenes are skipped; it continues from the first incomplete one  
4. `full-voiceover.wav` is rebuilt at the end  

Force everything to regenerate:

```bash
tools/piper-env/bin/python scripts/generate_voiceover.py \
  output/<slug>/03-voiceover.md --force
```

---

## Auto-push (do not lose a run)

Every pipeline run ends with `scripts/save_to_git.sh`. That script:

1. Adds `output/<slug>/01-research.md` through `04-video-prompts.md`
2. Commits with a message like `Save documentary package: jeffrey-dahmer`
3. Pulls with rebase (so two people do not overwrite each other)
4. Pushes the current branch to **whatever `origin` is on this machine**

It does **not** use one person’s SSH key. Whoever is signed in on that computer is who GitHub sees.

Audio WAVs, Piper models, and `.env` stay **local**. They are gitignored. The text history is what gets pushed.

You do not run this yourself when using the skill. To save a folder by hand:

```bash
bash scripts/save_to_git.sh the-silk-road-dark-web "the silk road - dark web"
```

### Shared repo: more than one person

Anyone on the team can push. Each person uses **their own** GitHub account.

**Repo owner (once):**

1. GitHub → the shared repo → **Settings → Collaborators**  
2. Invite each person (brother, teammate) with **Write** access  
3. They must accept the email/invite  

**Everyone else (each laptop, once):**

1. Create your own GitHub account if you do not have one  
2. Clone the **shared** repo (do not fork unless you want a private copy):

```bash
git clone git@github.com:OWNER/REPO.git
cd REPO
```

3. Sign **your** account into the CLI — not someone else’s key.

**SSH (preferred):**

```bash
ssh-keygen -t ed25519 -C "you@email.com"
# GitHub → your account → Settings → SSH and GPG keys → add ~/.ssh/id_ed25519.pub
ssh -T git@github.com
# Must print YOUR username, not a sibling’s
```

**Or GitHub CLI:**

```bash
brew install gh
gh auth login
```

4. Confirm `origin` is the shared repo, not a personal fork:

```bash
git remote -v
# origin  git@github.com:OWNER/REPO.git
```

If `origin` is missing:

```bash
git remote add origin git@github.com:OWNER/REPO.git
```

A **403** means this laptop’s GitHub user is not a collaborator, or it is logged in as the wrong account. The owner adds Write access; you sign in as the invited user. Do not copy someone else’s private SSH key.

If two people finish a run at the same time, the script rebases onto `origin` first. If that conflicts, the local commit is kept — resolve, then `git push`. The script never force-pushes.

---

## First-time setup

Step-by-step for **Windows + Blackwell (RTX 5080)** and **M-series Macs** is in **[INSTALL.md](INSTALL.md)**.

You need **Python 3.12** (3.14 can break Piper wheels).

### 1. Piper environment

```bash
cd /path/to/this/repo

python3.12 -m venv tools/piper-env
source tools/piper-env/bin/activate
pip install --upgrade pip
pip install piper-tts
```

### 2. Voices

```bash
mkdir -p tools/piper-voices
cd tools/piper-voices

# Deep male (default)
curl -L -o en_US-ryan-high.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx"
curl -L -o en_US-ryan-high.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx.json"

# Fallback
curl -L -o en_US-lessac-medium.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
curl -L -o en_US-lessac-medium.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
```

### 3. Local voices (Kokoro / Chatterbox / Orpheus)

```bash
bash scripts/setup_local_tts.sh
```

Uses CUDA 12.8 when `nvidia-smi` is present (RTX 5080). On a Mac it installs the CPU/MPS stack. The fully-acted voice needs CUDA + vLLM, so it may skip on macOS.

### 4. Smoke test

```bash
cd /path/to/this/repo
source tools/piper-env/bin/activate

echo "This is a test of the documentary voiceover." | \
  piper --model tools/piper-voices/en_US-ryan-high.onnx \
        --output_file /tmp/piper-test.wav

afplay /tmp/piper-test.wav
```

---

## Project layout

```
youtube/
  README.md
  INSTALL.md                    Windows Blackwell + M-series Mac voice setup
  Research.docx                 Original research prompt
  Script.docx                   Original script prompt
  Voice Over Script.docx        Original scene-split prompt
  Generate Video Prompts.docx   Original visual-prompt prompt

  scripts/
    generate_voiceover.py       Local + paid TTS + SQLite resume
    generate_video.py           HeyGen Video Agent clips + SQLite resume
    pipeline_lib.py             Topic parse, voice menu, key check, parsers
    setup_local_tts.sh                One-time Kokoro / Chatterbox / Orpheus venv
    require_github.sh                 Hard stop until GitHub CLI/SSH is signed in
    setup_github_gate_protection.sh   Install GitHub rulesets that reject gate removal
    save_to_git.sh                    Commit markdown + push after every run
    ../.github/workflows/
      protect-github-gate.yml         CI fails if the gate files are missing/hollowed out

  tools/
    piper-env/                  Python venv with piper-tts
    piper-voices/               .onnx voice models
    tts-env/                    Kokoro / Chatterbox / Orpheus (after setup)
    voices/                     optional narrator.wav clone clip

  .cursor/skills/youtube-documentary-pipeline/
    SKILL.md                    Cursor skill
    research-prompt.md
    script-prompt.md
    voiceover-prompt.md
    video-prompts.md

  .claude/skills/youtube-documentary-pipeline/
    SKILL.md                    Claude Code skill
    (same prompt files)

  output/
    <slug>/                     One folder per video
```

The `.docx` files are the original master prompts. The skill copies live in markdown next to `SKILL.md` and are what the agent follows.

---

## Pipeline details

### 1. Research

A full dossier, not a title list: confirmed facts, timeline, people, locations, documents, quotes, contradictions, theories, sources. Written so a 12–18 minute script can be drafted without another search.

### 2. Script

Calm, faceless documentary narration. No “hey guys”, no subscribe CTA, no headings. Length **15,000–18,000 characters**. Facts come only from the research.

### 3. Voiceover script

Every word of the script, split at natural breaks into ~**25 words / 10 seconds**. Markers:

- `(pause)` — about 0.45s  
- `(long pause)` — about 1.15s (hooks and endings)

### 4. Audio

`scripts/generate_voiceover.py` reads `03-voiceover.md` and writes WAVs. Local voices are free. The AI asks how it should sound, then passes `--provider`. ElevenLabs and HeyGen are optional and still need an explicit yes in chat.

### 5. Video prompts

One prompt per voiceover scene: narration copied exactly, plus setting, lighting, camera, mood. Style is dark, desaturated, true-crime documentary. These are meant for Runway, Kling, Pika, Luma, or Google Veo. If you say yes to HeyGen video, `scripts/generate_video.py` also renders a clip per scene.

---

## `generate_voiceover.py` flags

```bash
tools/piper-env/bin/python scripts/generate_voiceover.py INPUT.md [options]
# or tools/tts-env/bin/python for Kokoro / Chatterbox / Orpheus
```

| Flag | Meaning |
|---|---|
| `--from-topic "..."` | Parse story (and optional hidden provider) from the topic line |
| `--parse-topic "..."` | Print JSON and exit (no audio) |
| `--check-keys` | Print which paid API keys are set (JSON) and exit |
| `--voice-menu` | Plain-English sound options the AI should ask |
| `--resolve-intent "..."` | Map a chat reply to a provider (JSON) |
| `--provider ...` | `piper`, `kokoro`, `chatterbox`, `orpheus`, `elevenlabs`, `heygen` |
| `--voice NAME` | Engine voice name, alias, or ID |
| `--semitones -3.5` | Piper pitch (negative = deeper) |
| `--length-scale 1.15` | Piper speed (`>1` = slower) |
| `--exaggeration 0.4` | Chatterbox emotion |
| `--cfg-weight 0.45` | Chatterbox pacing |
| `--pause 0.45` | Silence after `(pause)` |
| `--long-pause 1.15` | Silence after `(long pause)` |
| `--no-deep` | Skip Piper pitch/warmth |
| `--force` | Ignore SQLite and regenerate every scene |
| `--output-dir DIR` | Where to write WAVs |

## `generate_video.py` flags

```bash
tools/piper-env/bin/python scripts/generate_video.py INPUT.md [options]
```

| Flag | Meaning |
|---|---|
| `--from-topic "..."` | Story title for clip names |
| `--check-keys` | Same key JSON as the voiceover script |
| `--voice ID` | Optional HeyGen voice ID for Video Agent |
| `--scenes 1-5` | Only these scene numbers |
| `--max-scenes N` | Stop after N new renders |
| `--force` | Ignore SQLite and re-render |
| `--output-dir DIR` | Where to write MP4s |

---

## What is not automated yet

- **Finished edit.** HeyGen can render per-scene clips if you say yes. You still assemble them under the voiceover (and can still use Flow / Veo / Kling / Runway from `04-video-prompts.md`).  
- **YouTube upload.**  
- **Background music.** `full-voiceover.wav` is dry narration.

---

## Notes

- Treat real victims and families with care. The prompts forbid invented quotes and sensational gore.  
- Local voices are unlimited and offline after setup. ElevenLabs bills per character; a 16k-character script is about one long video on a Starter plan. HeyGen bills for speech and for each Video Agent clip.  
- Large files live under `tools/piper-env/`, `tools/tts-env/`, `tools/piper-voices/`, and `output/`. Keep secrets in `.env`, not in git.
