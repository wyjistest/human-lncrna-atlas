#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORKFLOW_PATH="$REPO_ROOT/.github/workflows/governance-sync.yml"
EXPECTED_RUNS_ON="\${{ (github.event_name == 'workflow_dispatch' && github.event.inputs.runs_on) || vars.CI_RUNS_ON || 'ubuntu-latest' }}"

if grep -Fq "runs-on: \${{ env.CI_RUNS_ON }}" "$WORKFLOW_PATH"; then
  echo "governance-sync workflow must not use env context in job-level runs-on" >&2
  exit 1
fi

match_count="$(grep -Fc "runs-on: $EXPECTED_RUNS_ON" "$WORKFLOW_PATH" || true)"
if [ "$match_count" -ne 2 ]; then
  echo "expected governance-sync workflow to pin both jobs to the direct runs-on expression" >&2
  exit 1
fi

echo "OK: governance-sync workflow uses a valid job-level runs-on expression"
