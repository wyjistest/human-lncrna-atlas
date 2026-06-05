#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - `scripts/run-tests.sh scripts-tests` 是 scripts/tests 的统一入口。
# - 新增 shell 回归测试后必须被入口收录，避免 CI 与本地统一入口静默漂移。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

python3 - "$REPO_ROOT" <<'PY'
import re
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
run_tests = repo_root / "scripts/run-tests.sh"
listed = set(re.findall(r'"(scripts/tests/test_[^"]+\.sh)"', run_tests.read_text(encoding="utf-8")))
existing = {path.relative_to(repo_root).as_posix() for path in (repo_root / "scripts/tests").glob("test_*.sh")}

missing = sorted(existing - listed)
stale = sorted(listed - existing)

if missing or stale:
    if missing:
        print("scripts-tests is missing shell tests:", file=sys.stderr)
        for path in missing:
            print(f"- {path}", file=sys.stderr)
    if stale:
        print("scripts-tests lists missing shell tests:", file=sys.stderr)
        for path in stale:
            print(f"- {path}", file=sys.stderr)
    raise SystemExit(1)
PY

echo "OK: scripts-tests includes every scripts/tests shell regression"
