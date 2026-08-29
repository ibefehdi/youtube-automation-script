#!/usr/bin/env bash
# Commit pipeline output and push so a run is never only on one machine.
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

# Keep prompt/skill/script changes with the same run if they were edited.
git add -- \
  README.md \
  .gitignore \
  scripts/ \
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
  echo "No origin remote. Local commit kept; add origin to push." >&2
  exit 0
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if git push -u origin "$BRANCH"; then
  echo "Pushed $BRANCH to origin."
else
  echo "Push failed. Local commit is still here. Fix remote/SSH and run:" >&2
  echo "  git push -u origin $BRANCH" >&2
  exit 1
fi
