#!/usr/bin/env bash
# Scaffold of the eval case "ghost" (plan E9.6). Runs in the empty workspace before the agent,
# outside the sandbox, with no EVAL_* variables and a 120 s limit: it only copies from the cache
# that evals/setup.sh prepared, never installs anything.
set -euo pipefail
CACHE=/opt/tribunedesk-evals
CASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cat > README.md <<'EOF'
# Newsroom site

Our site runs on Ghost(Pro), the hosted Ghost service: we manage it in Ghost Admin and cannot run
our own code or plugins on its servers. Theme and content are edited in Ghost Admin.
EOF
git init -q
git config user.name "Eval Developer"
git config user.email "developer@example.com"
git add -A
git commit -qm "README"
