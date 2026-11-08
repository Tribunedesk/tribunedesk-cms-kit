#!/usr/bin/env bash
# Scaffold of the eval case "drupal-l12" (plan E9.6). Runs in the empty workspace before the agent,
# outside the sandbox, with no EVAL_* variables and a 120 s limit: it only copies from the cache
# that evals/setup.sh prepared, never installs anything.
set -euo pipefail
CACHE=/opt/tribunedesk-evals
CASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# vendor/ and web/core are hard links into the cache (read-only files; copying them does not fit
# in 120 s); everything Composer or the site writes is a real copy.
SRC="$CACHE/drupal"
tar -C "$SRC" --exclude=./vendor --exclude=./web/core -cf - . | tar -xf -
cp -al "$SRC/vendor" vendor
rm -rf vendor/composer vendor/autoload.php
cp -a "$SRC/vendor/composer" "$SRC/vendor/autoload.php" vendor/
cp -al "$SRC/web/core" web/core
chmod u+w web/sites/default web/sites/default/settings.php
sed -i "s#$SRC/web/##g" web/sites/default/settings.php
git init -q
git config user.name "Eval Developer"
git config user.email "developer@example.com"
git add -A
git commit -qm "Drupal 11 site"
