#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORKFLOW_PATH="$REPO_ROOT/.github/workflows/test.yml"

if grep -Fq "uses: gitleaks/gitleaks-action@v2" "$WORKFLOW_PATH"; then
  echo "secret-scan workflow must not depend on gitleaks-action@v2" >&2
  exit 1
fi

if ! grep -Fq "gitleaks git \\" "$WORKFLOW_PATH"; then
  echo "secret-scan workflow must run gitleaks git for repository history scanning" >&2
  exit 1
fi

if ! grep -Fq "gitleaks dir \\" "$WORKFLOW_PATH"; then
  echo "secret-scan workflow must keep filesystem fallback scanning" >&2
  exit 1
fi

if grep -Fq "gitleaks detect \\" "$WORKFLOW_PATH"; then
  echo "secret-scan workflow should use explicit git/dir commands instead of deprecated detect" >&2
  exit 1
fi

echo "OK: secret-scan workflow uses gitleaks CLI for both git and filesystem scanning"
