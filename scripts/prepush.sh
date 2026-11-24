#!/usr/bin/env bash
# Checks before every push: tests green, no secrets in new commits, no private or generated files tracked.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run pytest -q -p no:warnings
gitleaks git --log-opts="origin/main..HEAD" --no-banner --redact
if git ls-files | grep -E '(^|/)\.env$|docs/BRIEF\.md|^var/|^data/processed/[^.]' ; then
  echo "private or generated file is tracked" >&2
  exit 1
fi
echo "prepush ok"
