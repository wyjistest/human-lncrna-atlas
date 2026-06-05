#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - `run-tests.sh` 已有 Scripts smoke 阶段，应提供独立 CLI 模式。
# - 便于本地只运行离线脚本冒烟，而不必启动完整 `ci`。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

tmp_root="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_root"
}
trap cleanup EXIT

mkdir -p "$tmp_root/scripts/genomes/tests" "$tmp_root/scripts/research"
cp "$REPO_ROOT/scripts/run-tests.sh" "$tmp_root/scripts/run-tests.sh"
chmod +x "$tmp_root/scripts/run-tests.sh"

cat > "$tmp_root/scripts/genomes/tests/test_download_igv_assets.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "download igv assets ok"
EOF
chmod +x "$tmp_root/scripts/genomes/tests/test_download_igv_assets.sh"

cat > "$tmp_root/scripts/research/example_report.py" <<'EOF'
print("research syntax ok")
EOF

cat > "$tmp_root/scripts/research/generate_example_sample_baseline_local.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "research sample baseline ok"
EOF
chmod +x "$tmp_root/scripts/research/generate_example_sample_baseline_local.sh"

set +e
output="$(cd "$tmp_root" && bash scripts/run-tests.sh scripts-smoke 2>&1)"
status=$?
set -e

if [ "$status" -ne 0 ]; then
  echo "expected scripts-smoke mode to exit 0" >&2
  echo "$output" >&2
  exit 1
fi

echo "$output" | grep -F "脚本冒烟测试通过" >/dev/null || {
  echo "expected scripts-smoke mode to run script smoke tests" >&2
  echo "$output" >&2
  exit 1
}

set +e
usage_output="$(bash "$tmp_root/scripts/run-tests.sh" does-not-exist 2>&1)"
set -e

echo "$usage_output" | grep -F "scripts-smoke" >/dev/null || {
  echo "expected usage output to include scripts-smoke" >&2
  echo "$usage_output" >&2
  exit 1
}

echo "OK: run-tests exposes scripts-smoke mode"
