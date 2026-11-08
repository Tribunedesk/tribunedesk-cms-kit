#!/usr/bin/env bash
# Scaffold of the eval case "no-public-endpoint" (plan E9.6). Runs in the empty workspace before the agent,
# outside the sandbox, with no EVAL_* variables and a 120 s limit: it only copies from the cache
# that evals/setup.sh prepared, never installs anything.
set -euo pipefail
CACHE=/opt/tribunedesk-evals
CASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -a "$CACHE/django-blog/." .
ln -s "$CACHE/venvs/django" .venv
cat >> README.md <<'EOF'

## Deployment

Production runs on the newsroom intranet behind the company firewall. Nothing on the internet can
reach it; it may call out over https.
EOF
git init -q
git config user.name "Eval Developer"
git config user.email "developer@example.com"
git add -A
git commit -qm "Blog on the intranet"
