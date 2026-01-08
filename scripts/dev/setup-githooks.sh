#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

git config core.hooksPath .githooks
chmod +x .githooks/pre-push

echo "OK: git hooks enabled via core.hooksPath=.githooks"
echo "Pre-push will run CodeRabbit before allowing pushes."


