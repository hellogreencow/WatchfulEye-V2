#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[figma] Building React preview into ${ROOT_DIR}/docs (GitHub Pages friendly)"

cd "${ROOT_DIR}/frontend"

if [ -f package-lock.json ]; then
  npm ci
else
  npm install
fi

rm -rf build
PUBLIC_URL=. REACT_APP_FIGMA_MODE=true npm run build

cd "${ROOT_DIR}"
rm -rf docs
mkdir -p docs

# Copy CRA build output into /docs for GitHub Pages
cp -R frontend/build/* docs/

echo "[figma] Done. Commit and enable GitHub Pages from /docs."


