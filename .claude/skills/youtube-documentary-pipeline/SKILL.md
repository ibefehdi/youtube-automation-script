---
name: youtube-documentary-pipeline
description: >
  Runs the full faceless documentary pipeline from one topic: deep research
  dossier, 15k–18k narration script, 10-second voiceover scenes, Piper or
  ElevenLabs audio, then AI video prompts. Use when the user gives a topic
  (e.g. "jeffrey dahmer - elevenlabs"), asks to make a YouTube documentary,
  or generate voiceover / video prompts.
when_to_use: >
  Invoke when the user types a lone topic, asks for a faceless documentary,
  says "make the video", "run the pipeline", or mentions research + script +
  voiceover + video prompts in one request.
argument-hint: "[topic]"
allowed-tools: Read Write Edit Glob Grep WebSearch WebFetch Bash
---

# YouTube Documentary Pipeline

One topic in. Research, script, timed voiceover, spoken audio, then video prompts. Do not ask clarifying questions. Do not stop after titles or a summary.

## Topic syntax (hands-off)

The user never edits code. Provider and voice are in the topic line.

```
<story>
<story> - piper
<story> - elevenlabs
<story> - elevenlabs - <voice>
```

Examples:

- `the silk road - dark web` → local Piper, deep Ryan
- `jeffrey dahmer - elevenlabs` → ElevenLabs, default **Adam** (deep documentary male)
- `jeffrey dahmer - elevenlabs - daniel` → ElevenLabs Daniel
- `jeffrey dahmer - elevenlabs - deep male` → same as Adam

Voice after `elevenlabs` can be a name, an alias, or an ElevenLabs voice ID.

| Alias | Voice |
|---|---|
| *(omitted)*, adam, deep, deep male, documentary, narrator, rumble, youtube | Adam |
| daniel, news, british | Daniel |
| chris | Chris |
| antoni, warm | Antoni |
| josh | Josh |
| bill, gravel | Bill |

If they name a voice that is not in the table, the script searches their ElevenLabs account.

ElevenLabs needs `ELEVENLABS_API_KEY` in the environment or in `.env` / `tools/.env`. Do not ask them to edit Python.

## Input

The raw topic is:

$ARGUMENTS

If \$ARGUMENTS is empty, use the rest of the user message.

## First command

Parse the raw topic. Use this JSON for the story title, folder slug, provider, and voice. Do not put `elevenlabs` / `piper` / the voice name into the research topic.

```bash
${CLAUDE_PROJECT_DIR}/tools/piper-env/bin/python ${CLAUDE_PROJECT_DIR}/scripts/generate_voiceover.py --parse-topic "$ARGUMENTS"
```

## Output folder

Write under `${CLAUDE_PROJECT_DIR}/output/<slug>/`:

```
output/<slug>/
  01-research.md
  02-script.md
  03-voiceover.md
  audio/scene-001.wav ...
  audio/full-voiceover.wav
  audio/progress.sqlite
  04-video-prompts.md
```

Create the folder first. After the last file, reply with the paths, provider, voice, scene count, and audio runtime.

## Workflow

```
Pipeline:
- [ ] 0. Parse topic → story, slug, provider, voice
- [ ] 1. Research dossier → output/<slug>/01-research.md
- [ ] 2. Narration script → output/<slug>/02-script.md
- [ ] 3. Voiceover scenes → output/<slug>/03-voiceover.md
- [ ] 3b. Audio (immediately after 3) → output/<slug>/audio/
- [ ] 4. Video prompts → output/<slug>/04-video-prompts.md
- [ ] 5. Commit and push to git (always)
```

Prompt files live in `${CLAUDE_SKILL_DIR}/`.

### Step 1 — Research

Read `${CLAUDE_SKILL_DIR}/research-prompt.md`. Follow it exactly.

- Search the live web. Do not write the dossier from memory alone.
- Prefer court records, official reports, major newspapers, investigative longform, books, and recorded interviews.
- Output the **entire dossier**, not a title or idea list.
- Do not invent names, dates, quotes, numbers, or outcomes.

Write `01-research.md`. Continue. Do not wait.

### Step 2 — Script

Read `${CLAUDE_SKILL_DIR}/script-prompt.md`. Follow it exactly.

Input: title + case name + the **full** contents of `01-research.md`.

- 15,000–18,000 characters including spaces.
- Natural paragraphs only. After writing, count characters. Rewrite if outside range.

Write `02-script.md` as the script only.

### Step 3 — Voiceover script + audio

Read `${CLAUDE_SKILL_DIR}/voiceover-prompt.md`. Follow it exactly.

- Preserve every word from `02-script.md`.
- ~10-second scenes. End with `Total Scenes: [X]`.

Write `03-voiceover.md`. Then generate audio immediately:

```bash
${CLAUDE_PROJECT_DIR}/tools/piper-env/bin/python ${CLAUDE_PROJECT_DIR}/scripts/generate_voiceover.py ${CLAUDE_PROJECT_DIR}/output/<slug>/03-voiceover.md --from-topic "$ARGUMENTS"
```

SQLite at `output/<slug>/audio/progress.sqlite` skips finished scenes. If this command fails partway, run the **same** command again. Do not delete the audio folder.

If ElevenLabs is missing a key, say so and fall back to Piper only if the user did not explicitly ask for ElevenLabs.

### Step 4 — Video prompts

Read `${CLAUDE_SKILL_DIR}/video-prompts.md`. Follow it exactly.

- One prompt per scene. Copy narration exactly.
- Dark, moody documentary look. No gore, no text overlays.

Write `04-video-prompts.md` as the prompts only.

### Step 5 — Save history to git

Always run this after Step 4, even if audio had errors. Do not skip. Do not wait for the user.

```bash
bash ${CLAUDE_PROJECT_DIR}/scripts/save_to_git.sh <slug> "$ARGUMENTS"
```

This commits the markdown package (`01`–`04`) and pushes the current branch to `origin`. WAV files stay local (gitignored). If push fails, report the error; the local commit must still exist. Never force-push. Never skip hooks. Never change git config.

## Hard rules

- One topic → one story. Strip only the provider/voice suffix.
- Never stop at a title. Never invent facts.
- Treat real people with dignity.
- Always generate audio as soon as `03-voiceover.md` exists, before video prompts.
- Always commit and push after video prompts so the run is not only on one machine.
- Never ask the user to edit `generate_voiceover.py` to pick a voice.

## Example

User: `/youtube-documentary-pipeline jeffrey dahmer - elevenlabs`

Writes `output/jeffrey-dahmer/` with ElevenLabs Adam audio.
