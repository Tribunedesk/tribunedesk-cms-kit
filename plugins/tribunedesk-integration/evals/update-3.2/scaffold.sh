#!/usr/bin/env bash
# Scaffold of the eval case "update-3.2" (plan E9.6). Runs in the empty workspace before the agent,
# outside the sandbox, with no EVAL_* variables and a 120 s limit: it only copies from the cache
# that evals/setup.sh prepared, never installs anything.
set -euo pipefail
CACHE=/opt/tribunedesk-evals
CASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -a "$CACHE/django-blog/." .
ln -s "$CACHE/venvs/django" .venv
# The integration built for contract 3.2.0-draft (levels 1+2, webhook), with its manifest.
cp -a "$CASE_DIR/fixture/." .
git init -q
git config user.name "Eval Developer"
git config user.email "developer@example.com"
git add -A
git commit -qm "Blog with the Tribune Desk integration for contract 3.2.0-draft"
