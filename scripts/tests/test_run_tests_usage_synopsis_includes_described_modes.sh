#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - `run-tests.sh` usage 第一行的模式列表必须包含后续说明里的模式。
# - 避免可用模式（如 ci-plus / ci-full）只在说明中出现，却不在 synopsis 中出现。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

set +e
out="$(bash "$REPO_ROOT/scripts/run-tests.sh" __usage_probe__ 2>&1)"
set -e

python3 - "$out" <<'PY'
import re
import sys

usage = sys.argv[1]
synopsis_match = re.search(r"用法: .* \[([^\]]+)\]", usage)
if not synopsis_match:
    raise SystemExit("missing usage synopsis")

synopsis_modes = set(synopsis_match.group(1).split("|"))
described_modes = set(re.findall(r"^  ([a-z0-9-]+)\s+-", usage, flags=re.MULTILINE))
missing = sorted(described_modes - synopsis_modes)
if missing:
    raise SystemExit("usage synopsis is missing described modes: " + ", ".join(missing))
PY

echo "OK: run-tests usage synopsis includes every described mode"
