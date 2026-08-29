#!/usr/bin/env bash
# Create GitHub rulesets so pushes that remove/change the GitHub hard-gate are rejected.
# Requires: gh auth login (admin on the repo)
# Usage: bash scripts/setup_github_gate_protection.sh
#
# Collaborators with Write cannot delete or edit the gate files — GitHub rejects the push.
# Repo admins can still bypass to update the gate intentionally.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v gh >/dev/null 2>&1; then
  echo "Install GitHub CLI first: https://cli.github.com/" >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Run: gh auth login" >&2
  exit 1
fi

REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
echo "Configuring hard-gate protection on $REPO"

python - "$REPO" <<'PY'
import json, subprocess, sys

repo = sys.argv[1]

protected_paths = [
    "scripts/require_github.sh",
    ".claude/skills/youtube-documentary-pipeline/SKILL.md",
    ".cursor/skills/youtube-documentary-pipeline/SKILL.md",
    ".github/workflows/protect-github-gate.yml",
    "scripts/setup_github_gate_protection.sh",
]

# Admin role can bypass so the owner can still update the gate on purpose.
bypass = [
    {
        "actor_id": 5,
        "actor_type": "RepositoryRole",
        "bypass_mode": "always",
    }
]


def api(method, path, body=None):
    cmd = ["gh", "api", "--method", method, path]
    if body is not None:
        cmd.extend(["--input", "-"])
    proc = subprocess.run(
        cmd,
        input=None if body is None else json.dumps(body).encode(),
        capture_output=True,
    )
    out = (proc.stdout or b"").decode()
    err = (proc.stderr or b"").decode()
    if proc.returncode != 0:
        raise RuntimeError(f"{method} {path} failed:\n{err or out}")
    return json.loads(out) if out.strip() else None


def upsert(name, body):
    rulesets = api("GET", f"repos/{repo}/rulesets") or []
    existing = next((r for r in rulesets if r.get("name") == name), None)
    if existing:
        print(f'Updating ruleset "{name}" (id={existing["id"]})')
        return api("PUT", f"repos/{repo}/rulesets/{existing['id']}", body)
    print(f'Creating ruleset "{name}"')
    return api("POST", f"repos/{repo}/rulesets", body)


push_name = "Hard gate — reject path changes"
push_body = {
    "name": push_name,
    "target": "push",
    "enforcement": "active",
    "conditions": {
        "ref_name": {
            "include": ["~ALL"],
            "exclude": [],
        }
    },
    "rules": [
        {
            "type": "file_path_restriction",
            "parameters": {"restricted_file_paths": protected_paths},
        }
    ],
    "bypass_actors": bypass,
}

push_ok = False
try:
    upsert(push_name, push_body)
    push_ok = True
    print("Push path restriction is active — removing the gate will be rejected.")
except RuntimeError as e:
    print(f"\nWARN: Push ruleset failed:\n{e}")
    print("Private repos often need GitHub Pro for push rules.")
    print("Falling back to branch ruleset with required status check.")

branch_name = "Hard gate — main protection"
branch_rules = [{"type": "non_fast_forward"}]
if not push_ok:
    branch_rules.append(
        {
            "type": "required_status_checks",
            "parameters": {
                "strict_required_status_checks_policy": True,
                "do_not_enforce_on_create": False,
                "required_status_checks": [
                    {"context": "GitHub gate files required"}
                ],
            },
        }
    )

upsert(
    branch_name,
    {
        "name": branch_name,
        "target": "branch",
        "enforcement": "active",
        "conditions": {
            "ref_name": {
                "include": ["refs/heads/main", "refs/heads/master"],
                "exclude": [],
            }
        },
        "rules": branch_rules,
        "bypass_actors": bypass,
    },
)

print(f"\nDone. List rulesets with: gh api repos/{repo}/rulesets")
print("Pipeline pushes of research/scripts are unchanged;")
print("only edits that touch the GitHub hard-gate files are blocked.")
PY
