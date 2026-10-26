#!/usr/bin/env bash
# Build musebreak-ultimate.tar.gz from git-tracked files only (excludes node_modules, .git, .next, caches, gitignored shots).
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${1:-../musebreak-ultimate.tar.gz}"
git ls-files -z | tar --null -czf "$OUT" --transform 's,^,musebreak/,' -T -
echo "wrote $OUT ($(git ls-files | wc -l) files)"
