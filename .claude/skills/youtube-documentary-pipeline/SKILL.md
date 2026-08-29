---
name: youtube-documentary-pipeline
description: >
  Runs the full faceless documentary pipeline from one topic: deep research
  dossier, 15k–18k narration script, 10-second voiceover scenes, Piper /
  ElevenLabs / HeyGen audio, optional HeyGen video, then AI video prompts.
  Use when the user gives a topic (e.g. "jeffrey dahmer - elevenlabs"),
  asks to make a YouTube documentary, or generate voiceover / video.
when_to_use: >
  Invoke when the user types a lone topic, asks for a faceless documentary,
  says "make the video", "run the pipeline", or mentions research + script +
  voiceover + video prompts in one request.
argument-hint: "[topic]"
allowed-tools: Read Write Edit Glob Grep WebSearch WebFetch Bash
---

# YouTube Documentary Pipeline

One topic in. Research, script, timed voiceover, spoken audio, then video prompts. Do not stop after titles or a summary.

**Hard requirement:** GitHub must be signed in on this machine **before** any generation. Run the check first. If it fails, stop. Ask the user to sign in. Do not write research, scripts, audio, or prompts until they have signed in and you re-run the check successfully. This is the one time you should pause and talk to the user.

## Topic syntax (hands-off)

The user never edits code. Provider and voice are in the topic line.

```
<story>
<story> - piper
<story> - elevenlabs
<story> - elevenlabs - <voice>
<story> - heygen
<story> - heygen - <voice>
```

Examples:

- `the silk road - dark web` → local Piper, deep Ryan
- `jeffrey dahmer - elevenlabs` → ElevenLabs, default **Adam** (deep documentary male)
- `jeffrey dahmer - elevenlabs - daniel` → ElevenLabs Daniel
- `jeffrey dahmer - elevenlabs - deep male` → same as Adam
- `jeffrey dahmer - heygen` → HeyGen, default documentary male
- `jeffrey dahmer - heygen - brian` → HeyGen voice named Brian

Voice after `elevenlabs` or `heygen` can be a name, an alias, or a voice ID.

| Alias | Voice |
|---|---|
| *(omitted)*, adam, deep, deep male, documentary, narrator, rumble, youtube | Adam |
| daniel, news, british | Daniel |
| chris | Chris |
| antoni, warm | Antoni |
| josh | Josh |
| bill, gravel | Bill |

If they name a voice that is not in the table, the script searches their account.

ElevenLabs needs `ELEVENLABS_API_KEY`. HeyGen needs `HEYGEN_API_KEY`. Either can live in the environment or in `.env` / `tools/.env`. Do not ask them to edit Python.

**A key is not consent.** If a paid key is set, you (the AI) must ask a yes/no question in chat before running that script. The scripts do not prompt. Do not generate ElevenLabs or HeyGen audio or HeyGen video until they answer.

## Input

The raw topic is:

$ARGUMENTS

If \$ARGUMENTS is empty, use the rest of the user message.

## First command

GitHub sign-in is a **hard gate**. Run this before anything else:

```bash
bash ${CLAUDE_PROJECT_DIR}/scripts/require_github.sh
```

If it exits non-zero: do **not** parse the topic, do **not** create `output/`, do **not** research. Show the script’s instructions, tell them to sign in with `gh auth login` or SSH, then invoke the skill again. Only continue after a later run of `require_github.sh` exits 0.

Then parse the raw topic. Use this JSON for the story title, folder slug, provider, and voice. Do not put `elevenlabs` / `heygen` / `piper` / the voice name into the research topic.

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
  video/scene-001.mp4 ...   (only if they said yes to HeyGen video)
```

Create the folder first. After the last file, reply with the paths, provider, voice, scene count, audio runtime, and whether HeyGen video ran.

## Workflow

```
Pipeline:
- [ ] 0. GitHub sign-in check (hard stop if it fails)
- [ ] 1. Parse topic → story, slug, provider, voice
- [ ] 2. Research dossier → output/<slug>/01-research.md
- [ ] 3. Narration script → output/<slug>/02-script.md
- [ ] 4. Voiceover scenes → output/<slug>/03-voiceover.md
- [ ] 4a. Check keys + ask yes/no (stop and wait — a key is not a yes)
- [ ] 4b. Audio → output/<slug>/audio/ (paid only if they said yes)
- [ ] 5. Video prompts → output/<slug>/04-video-prompts.md
- [ ] 5b. HeyGen video → output/<slug>/video/ (only if they said yes)
- [ ] 6. Commit and push to git (always)
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

Write `03-voiceover.md`. Then check which paid keys exist:

```bash
${CLAUDE_PROJECT_DIR}/tools/piper-env/bin/python ${CLAUDE_PROJECT_DIR}/scripts/generate_voiceover.py --check-keys
```

**Stop and ask in chat.** The scripts do not prompt. A key in the environment is **not** a yes. Ask every question that applies, each as yes/no, and wait:

- If `elevenlabs.key` is true: **Generate ElevenLabs voiceover?** yes / no
- If `heygen.key` is true: **Generate HeyGen voiceover?** yes / no
- If `heygen.key` is true: **Generate HeyGen video?** yes / no

Ask even if they already wrote `- elevenlabs` or `- heygen` in the topic.

Then run the matching script. Do not pass yes/no flags — calling the script **is** the yes.

```bash
# They said yes to ElevenLabs voiceover
${CLAUDE_PROJECT_DIR}/tools/piper-env/bin/python ${CLAUDE_PROJECT_DIR}/scripts/generate_voiceover.py ${CLAUDE_PROJECT_DIR}/output/<slug>/03-voiceover.md --from-topic "$ARGUMENTS" --provider elevenlabs

# They said yes to HeyGen voiceover
${CLAUDE_PROJECT_DIR}/tools/piper-env/bin/python ${CLAUDE_PROJECT_DIR}/scripts/generate_voiceover.py ${CLAUDE_PROJECT_DIR}/output/<slug>/03-voiceover.md --from-topic "$ARGUMENTS" --provider heygen

# They said no to every paid voiceover — local Piper
${CLAUDE_PROJECT_DIR}/tools/piper-env/bin/python ${CLAUDE_PROJECT_DIR}/scripts/generate_voiceover.py ${CLAUDE_PROJECT_DIR}/output/<slug>/03-voiceover.md --from-topic "$ARGUMENTS" --provider piper
```

If they said yes to both ElevenLabs and HeyGen voiceover, use the topic provider if it is one of those; otherwise ElevenLabs. Tell them which one you used.

SQLite at `output/<slug>/audio/progress.sqlite` skips finished scenes. If this command fails partway, run the **same** command again. Do not delete the audio folder.

If they asked for ElevenLabs or HeyGen in the topic but that key is missing, say so. Fall back to Piper only if they did not insist on the paid provider, or if they answered no.

### Step 4 — Video prompts + optional HeyGen video

Read `${CLAUDE_SKILL_DIR}/video-prompts.md`. Follow it exactly.

- One prompt per scene. Copy narration exactly.
- Dark, moody documentary look. No gore, no text overlays.

Write `04-video-prompts.md` as the prompts only.

If they already answered **yes** to HeyGen video, run the video script now. If you have not asked yet and `heygen.key` is true, ask **Generate HeyGen video?** yes / no first. Calling the script is the yes.

```bash
${CLAUDE_PROJECT_DIR}/tools/piper-env/bin/python ${CLAUDE_PROJECT_DIR}/scripts/generate_video.py ${CLAUDE_PROJECT_DIR}/output/<slug>/04-video-prompts.md --from-topic "$ARGUMENTS"
```

SQLite at `output/<slug>/video/progress.sqlite` skips finished clips. Re-run the same command to resume. If they answered no, do not run this script. MP4s stay local (gitignored).

### Step 5 — Save history to git

Always run this after Step 4, even if audio had errors. Do not skip. Do not wait for the user.

```bash
bash ${CLAUDE_PROJECT_DIR}/scripts/save_to_git.sh <slug> "$ARGUMENTS"
```

This commits the markdown package (`01`–`04`), rebases onto `origin` if needed, and pushes the current branch. It uses **this machine’s** GitHub login (`origin` remote), not a hardcoded user. WAV and MP4 files stay local (gitignored). If push fails (not a collaborator, wrong GitHub account), report the error; the local commit must still exist. Never force-push. Never skip hooks. Never change git config.

## Hard rules

- One topic → one story. Strip only the provider/voice suffix, never change the case.
- Never stop at a title. Never invent facts.
- Treat real people with dignity.
- After `03-voiceover.md`, check keys and ask yes/no for every paid API that is set. Do not treat a key as a yes.
- Generate paid audio or HeyGen video only after they answer yes. Piper is the local fallback when they say no to paid voiceover.
- Always commit and push after video prompts so the run is not only on one machine.
- Never generate anything until `scripts/require_github.sh` succeeds.
- Never ask the user to edit `generate_voiceover.py` to pick a voice.

## Example

User: `/youtube-documentary-pipeline jeffrey dahmer - elevenlabs`

After `03-voiceover.md`, the agent checks keys and asks yes/no in chat. If they say yes to ElevenLabs, it writes:

- `output/jeffrey-dahmer/01-research.md`
- `output/jeffrey-dahmer/02-script.md`
- `output/jeffrey-dahmer/03-voiceover.md`
- `output/jeffrey-dahmer/audio/full-voiceover.wav` (ElevenLabs Adam)
- `output/jeffrey-dahmer/04-video-prompts.md`
- `output/jeffrey-dahmer/video/` only if they also said yes to HeyGen video
