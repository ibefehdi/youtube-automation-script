# Faceless Documentary Pipeline

Give this project **one topic**. It turns that topic into a full YouTube documentary package:

1. Deep research dossier  
2. 15,000–18,000 character narration script  
3. Timed 10-second voiceover scenes  
4. Spoken audio (local Piper or ElevenLabs)  
5. AI video prompts for every scene (Runway, Kling, Pika, Luma, Veo)

You do not edit code to pick a voice or a provider. That is all in the topic line.

```
the silk road - dark web
jeffrey dahmer - elevenlabs
jeffrey dahmer - elevenlabs - daniel
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
@youtube-documentary-pipeline jeffrey dahmer - elevenlabs
```

### In Claude Code

```
/youtube-documentary-pipeline the silk road - dark web
```

The agent researches the story, writes the script, splits the voiceover, generates audio, then writes video prompts. It should not stop for approval between steps.

### Audio only (if the markdown already exists)

```bash
cd /Users/fahadasad/Downloads/youtube

# Local Piper (free)
tools/piper-env/bin/python scripts/generate_voiceover.py \
  output/the-silk-road-dark-web/03-voiceover.md

# ElevenLabs (from the same topic line)
tools/piper-env/bin/python scripts/generate_voiceover.py \
  output/the-silk-road-dark-web/03-voiceover.md \
  --from-topic "the silk road - dark web - elevenlabs"
```

Listen:

```bash
afplay output/the-silk-road-dark-web/audio/full-voiceover.wav
```

---

## Topic syntax

The last `- piper` or `- elevenlabs` is a **flag**, not part of the story. Everything before it is the case you want researched.

| You type | Story researched | Audio |
|---|---|---|
| `the silk road - dark web` | Silk Road | Piper (default) |
| `the silk road - dark web - piper` | Silk Road | Piper |
| `jeffrey dahmer - elevenlabs` | Jeffrey Dahmer | ElevenLabs **Adam** |
| `jeffrey dahmer - elevenlabs - daniel` | Jeffrey Dahmer | ElevenLabs Daniel |
| `jeffrey dahmer - elevenlabs - deep male` | Jeffrey Dahmer | ElevenLabs Adam |
| `el chapo - elevenlabs - pNInz6obpgDQGcFmaJgB` | El Chapo | That voice ID |

Check what a line will do without generating audio:

```bash
tools/piper-env/bin/python scripts/generate_voiceover.py \
  --parse-topic "jeffrey dahmer - elevenlabs - daniel"
```

```json
{
  "topic": "jeffrey dahmer",
  "slug": "jeffrey-dahmer",
  "provider": "elevenlabs",
  "voice": "daniel"
}
```

The folder name is always the **story slug**, never `jeffrey-dahmer-elevenlabs`.

---

## Voices

### Piper (local, free)

Default. Runs on your Mac. No API key.

- Voice: `en_US-ryan-high` (male narrator)
- Then pitched down **3.5 semitones** and slowed **15%** so it sits closer to a faceless-channel rumble
- Fallback if Ryan is missing: `en_US-lessac-medium`

Make it even deeper on a one-off run:

```bash
tools/piper-env/bin/python scripts/generate_voiceover.py \
  output/the-silk-road-dark-web/03-voiceover.md \
  --semitones -5
```

### ElevenLabs (paid, higher quality)

Needs a key once:

```bash
echo 'ELEVENLABS_API_KEY=your_key_here' >> .env
```

or:

```bash
export ELEVENLABS_API_KEY=your_key_here
```

The file can also live at `tools/.env`. Do not commit the key.

If you only write `- elevenlabs` and nothing else, the voice is **Adam** (deep documentary male). You pick a different voice in the topic, not in code.

| What you type after `- elevenlabs -` | Voice |
|---|---|
| *(nothing)*, `adam`, `deep`, `deep male`, `documentary`, `narrator`, `rumble`, `youtube` | Adam |
| `daniel`, `news`, `british` | Daniel |
| `chris` | Chris |
| `antoni`, `warm` | Antoni |
| `josh` | Josh |
| `bill`, `gravel` | Bill |
| any other name | Searched in your ElevenLabs account |
| a voice ID | Used as-is |

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

## First-time setup

You need **Python 3.12** (3.14 can break Piper wheels).

### 1. Piper environment

```bash
cd /Users/fahadasad/Downloads/youtube

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

### 3. Smoke test

```bash
cd /Users/fahadasad/Downloads/youtube
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
  Research.docx                 Original research prompt
  Script.docx                   Original script prompt
  Voice Over Script.docx        Original scene-split prompt
  Generate Video Prompts.docx   Original visual-prompt prompt

  scripts/
    generate_voiceover.py       Piper + ElevenLabs + SQLite resume

  tools/
    piper-env/                  Python venv with piper-tts
    piper-voices/               .onnx voice models

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

`scripts/generate_voiceover.py` reads `03-voiceover.md` and writes WAVs. Piper is local and free. ElevenLabs is optional and selected in the topic line.

### 5. Video prompts

One prompt per voiceover scene: narration copied exactly, plus setting, lighting, camera, mood. Style is dark, desaturated, true-crime documentary. These are meant for Runway, Kling, Pika, Luma, or Google Veo. **Google Flow has no public API**; clip generation is still a separate step.

---

## `generate_voiceover.py` flags

```bash
tools/piper-env/bin/python scripts/generate_voiceover.py INPUT.md [options]
```

| Flag | Meaning |
|---|---|
| `--from-topic "..."` | Parse provider + voice from the topic line |
| `--parse-topic "..."` | Print JSON and exit (no audio) |
| `--provider piper \| elevenlabs` | Override provider |
| `--voice NAME` | Piper model, ElevenLabs alias, name, or ID |
| `--semitones -3.5` | Piper pitch (negative = deeper) |
| `--length-scale 1.15` | Piper speed (`>1` = slower) |
| `--pause 0.45` | Silence after `(pause)` |
| `--long-pause 1.15` | Silence after `(long pause)` |
| `--no-deep` | Skip Piper pitch/warmth |
| `--force` | Ignore SQLite and regenerate every scene |
| `--output-dir DIR` | Where to write WAVs |

---

## What is not automated yet

- **Finished video.** You still generate clips in Flow / Veo / Kling / Runway from `04-video-prompts.md`, then edit them under the voiceover.  
- **YouTube upload.**  
- **Background music.** `full-voiceover.wav` is dry narration.

A practical next step is: clip API (Veo or Kling) → `ffmpeg` to lay each clip under each scene WAV → concat.

---

## Notes

- Treat real victims and families with care. The prompts forbid invented quotes and sensational gore.  
- Piper is unlimited and offline. ElevenLabs bills per character; a 16k-character script is about one long video on a Starter plan.  
- Large files live under `tools/piper-env/`, `tools/piper-voices/`, and `output/`. Keep secrets in `.env`, not in git.
