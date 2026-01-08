#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

if [[ ! -f .githooks/pre-push ]]; then
  echo "ERROR: .githooks/pre-push not found"
  exit 1
fi

git config core.hooksPath .githooks
chmod +x .githooks/pre-push

echo "OK: git hooks enabled via core.hooksPath=.githooks"
echo "Pre-push will run CodeRabbit before allowing pushes."


