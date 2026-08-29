#!/usr/bin/env bash
# Hard gate: GitHub must be signed in on this machine before the pipeline runs.
# Usage: scripts/require_github.sh
# Exit 0 = ok to generate. Exit 1 = stop and ask the user to sign in.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

fail() {
  cat >&2 <<'EOF'

GitHub sign-in is required before this pipeline can run.
Nothing will be generated until this machine is logged in as YOUR GitHub account.

Option A — GitHub CLI (easiest):
  brew install gh
  gh auth login
  gh auth status

Option B — SSH:
  ssh-keygen -t ed25519 -C "you@email.com"
  # Add ~/.ssh/id_ed25519.pub at GitHub → Settings → SSH and GPG keys
  ssh -T git@github.com
  # Must print: Hi YOUR_USERNAME! You've successfully authenticated...

Also required:
  git remote -v
  # origin must point at the shared repo, e.g. git@github.com:OWNER/REPO.git

If you were invited as a collaborator, accept the GitHub invite first.
Do not use someone else's SSH key.

When that succeeds, invoke the skill again with the same topic.
EOF
  exit 1
}

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "This folder is not a git repo. Clone the shared GitHub repo first." >&2
  fail
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  echo "No git remote named origin. Clone the shared repo, or: git remote add origin git@github.com:OWNER/REPO.git" >&2
  fail
fi

ORIGIN="$(git remote get-url origin)"
echo "origin: $ORIGIN"

signed_in=0
identity=""

try_ssh() {
  local ssh_out
  ssh_out="$(ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new -T git@github.com 2>&1 || true)"
  if echo "$ssh_out" | grep -qi "successfully authenticated"; then
    signed_in=1
    identity="$(echo "$ssh_out" | sed -n 's/.*Hi \([^!]*\)!.*/\1/p')"
    echo "GitHub SSH signed in as: ${identity:-unknown}"
    return 0
  fi
  echo "$ssh_out" >&2
  return 1
}

try_gh() {
  if ! command -v gh >/dev/null 2>&1; then
    return 1
  fi
  if gh auth status >/dev/null 2>&1; then
    signed_in=1
    identity="$(gh api user --jq .login 2>/dev/null || echo "gh")"
    echo "GitHub CLI signed in as: $identity"
    return 0
  fi
  return 1
}

# Prefer the method that matches origin, so the check is the same account that will push.
if [[ "$ORIGIN" == git@* || "$ORIGIN" == ssh://* ]]; then
  try_ssh || try_gh || true
else
  try_gh || try_ssh || true
fi

if [[ "$signed_in" -eq 0 ]]; then
  echo "No GitHub session on this machine." >&2
  fail
fi

echo "GitHub check passed. Pipeline may continue."
exit 0
