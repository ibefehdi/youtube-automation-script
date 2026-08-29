---
name: youtube-documentary-pipeline
description: >-
  Runs the full faceless documentary pipeline from one topic: deep research
  dossier, 15k–18k narration script, 10-second voiceover scenes, Piper or
  ElevenLabs audio, then AI video prompts. Use when the user gives a topic
  (e.g. "jeffrey dahmer - elevenlabs"), asks to make a YouTube documentary,
  or generate voiceover / video prompts.
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

## First command

GitHub sign-in is a **hard gate**. Run this before anything else:

```bash
bash scripts/require_github.sh
```

If it exits non-zero: do **not** parse the topic, do **not** create `output/`, do **not** research. Show the script’s instructions, tell them to sign in with `gh auth login` or SSH, then invoke the skill again. Only continue after a later run of `require_github.sh` exits 0.

Then parse the raw user message. Use this JSON for the story title, folder slug, provider, and voice. Do not put `elevenlabs` / `piper` / the voice name into the research topic.

```bash
tools/piper-env/bin/python scripts/generate_voiceover.py --parse-topic "<raw user topic>"
```

## Output folder

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
- [ ] 0. GitHub sign-in check (hard stop if it fails)
- [ ] 1. Parse topic → story, slug, provider, voice
- [ ] 2. Research dossier → output/<slug>/01-research.md
- [ ] 3. Narration script → output/<slug>/02-script.md
- [ ] 4. Voiceover scenes → output/<slug>/03-voiceover.md
- [ ] 4b. Audio (immediately after 4) → output/<slug>/audio/
- [ ] 5. Video prompts → output/<slug>/04-video-prompts.md
- [ ] 6. Commit and push to git (always)
```

### Step 1 — Research

Read [research-prompt.md](research-prompt.md). Follow it exactly.

- Search the live web. Do not write the dossier from memory alone.
- Prefer court records, official reports, major newspapers, investigative longform, books, and recorded interviews.
- Wikipedia is only a pointer to better sources.
- Output the **entire dossier**, not a title or idea list.
- Do not invent names, dates, quotes, numbers, or outcomes.

Write `01-research.md`. Continue. Do not wait.

### Step 2 — Script

Read [script-prompt.md](script-prompt.md). Follow it exactly.

Input: title + case name + the **full** contents of `01-research.md`.

- 15,000–18,000 characters including spaces.
- Natural paragraphs only. No headings, bullets, CTAs.
- After writing, count characters. Rewrite if outside range.

Write `02-script.md` as the script only.

### Step 3 — Voiceover script + audio

Read [voiceover-prompt.md](voiceover-prompt.md). Follow it exactly.

- Preserve every word from `02-script.md`.
- ~10-second scenes (~25 words). End with `Total Scenes: [X]`.

Write `03-voiceover.md`. Then generate audio immediately. Always pass the raw user topic so provider/voice stay in the prompt:

```bash
tools/piper-env/bin/python scripts/generate_voiceover.py output/<slug>/03-voiceover.md --from-topic "<raw user topic>"
```

SQLite at `output/<slug>/audio/progress.sqlite` skips finished scenes. If this command fails partway, run the **same** command again. Do not delete the audio folder.

If ElevenLabs is missing a key, say so and fall back to Piper only if the user did not explicitly ask for ElevenLabs.

### Step 4 — Video prompts

Read [video-prompts.md](video-prompts.md). Follow it exactly.

Input: full `03-voiceover.md`. Use visual notes from `01-research.md`.

- One prompt per scene. Copy narration exactly.
- Dark, moody documentary look. No gore, no text overlays.

Write `04-video-prompts.md` as the prompts only.

### Step 5 — Save history to git

Always run this after Step 4, even if audio had errors. Do not skip. Do not wait for the user.

```bash
bash scripts/save_to_git.sh <slug> "<raw user topic>"
```

This commits the markdown package (`01`–`04`), rebases onto `origin` if needed, and pushes the current branch. It uses **this machine’s** GitHub login (`origin` remote), not a hardcoded user. WAV files stay local (gitignored). If push fails (not a collaborator, wrong GitHub account), report the error; the local commit must still exist. Never force-push. Never skip hooks. Never change git config.

## Hard rules

- One topic → one story. Strip only the provider/voice suffix, never change the case.
- Never stop at a title. Never invent facts.
- Treat real people with dignity.
- Always generate audio as soon as `03-voiceover.md` exists, before video prompts.
- Always commit and push after video prompts so the run is not only on one machine.
- Never generate anything until `scripts/require_github.sh` succeeds.
- Never ask the user to edit `generate_voiceover.py` to pick a voice.

## Example

User: `jeffrey dahmer - elevenlabs`

Agent researches Jeffrey Dahmer, then writes:

- `output/jeffrey-dahmer/01-research.md`
- `output/jeffrey-dahmer/02-script.md`
- `output/jeffrey-dahmer/03-voiceover.md`
- `output/jeffrey-dahmer/audio/full-voiceover.wav` (ElevenLabs Adam)
- `output/jeffrey-dahmer/04-video-prompts.md`
