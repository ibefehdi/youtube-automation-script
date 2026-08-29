#!/usr/bin/env bash
# Commit pipeline output and push as whoever is signed in on this machine.
# Does not assume a specific GitHub user or SSH key.
# Usage: scripts/save_to_git.sh <slug> [topic]
set -euo pipefail

SLUG="${1:-}"
TOPIC="${2:-$SLUG}"

if [[ -z "$SLUG" ]]; then
  echo "Usage: scripts/save_to_git.sh <slug> [topic]" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not a git repository. Skipping save." >&2
  exit 0
fi

if [[ -d "output/$SLUG" ]]; then
  git add -- "output/$SLUG/"*.md 2>/dev/null || true
fi

git add -- \
  README.md \
  .gitignore \
  scripts/ \
  tools/voices/narrator.wav \
  .cursor/skills/youtube-documentary-pipeline/ \
  .claude/skills/youtube-documentary-pipeline/ \
  2>/dev/null || true

if git diff --cached --quiet; then
  echo "No new files to commit for $SLUG."
else
  git commit -m "$(cat <<EOF
Save documentary package: $SLUG

$TOPIC
EOF
)"
  echo "Committed $SLUG."
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  echo "No origin remote. Local commit kept." >&2
  echo "Each person: clone the shared repo, or run: git remote add origin git@github.com:OWNER/REPO.git" >&2
  exit 0
fi

ORIGIN="$(git remote get-url origin)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
echo "Pushing $BRANCH to $ORIGIN as this machine's GitHub login (not a shared key)."

if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
  if ! git pull --rebase --autostash origin "$BRANCH"; then
    echo "Could not rebase onto origin/$BRANCH. Local commit is kept." >&2
    echo "If two people pushed at once, resolve the rebase, then: git push origin $BRANCH" >&2
    exit 1
  fi
elif git ls-remote --exit-code origin "$BRANCH" >/dev/null 2>&1; then
  if ! git pull --rebase --autostash origin "$BRANCH"; then
    echo "Could not rebase onto origin/$BRANCH. Local commit is kept." >&2
    exit 1
  fi
fi

if git push -u origin "$BRANCH"; then
  echo "Pushed $BRANCH to origin."
else
  echo "Push failed. Local commit is still here." >&2
  echo "Typical causes:" >&2
  echo "  - This computer is not signed in to GitHub (ssh -T git@github.com  or  gh auth login)" >&2
  echo "  - Your GitHub user is not a collaborator on $ORIGIN (ask the repo owner for Write access)" >&2
  echo "  - CLI is logged in as a different GitHub account than the one that was invited" >&2
  echo "Then run: git push -u origin $BRANCH" >&2
  exit 1
fi
