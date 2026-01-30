#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 为 self-hosted runner 提供一个可复用、可审计的 “tarball checkout” 脚本：scripts/ci/checkout_tarball.sh
# - 覆盖关键分支：快路径（已有 .git 且 SHA 命中）、tarball 成功替换、tarball 无效、tarball 无顶层目录
#
# 说明：
# - 本测试不触网：通过注入 fake curl 生成/写入 tarball 文件。
# - 使用真实 tar 来构造最小 tar.gz（避免依赖 GNU tar 特性以外的行为）。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT_UNDER_TEST="$REPO_ROOT/scripts/ci/checkout_tarball.sh"

if [ ! -x "$SCRIPT_UNDER_TEST" ]; then
  echo "missing script under test: $SCRIPT_UNDER_TEST" >&2
  exit 1
fi

tmp_root="$(mktemp -d)"
cleanup() {
  if [ -n "${tmp_root:-}" ] && [ -d "${tmp_root:-}" ] && [ "${tmp_root:-}" != "/" ]; then
    rm -rf "$tmp_root"
  fi
}
trap cleanup EXIT

fake_bin="$tmp_root/bin"
mkdir -p "$fake_bin"

curl_called_file="$tmp_root/curl-called"
fake_tarball_file="$tmp_root/fake.tar.gz"

cat > "$fake_bin/curl" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

called_file="${FAKE_CURL_CALLED_FILE:?}"
tarball_file="${FAKE_CURL_TARBALL_FILE:?}"
mode="${FAKE_CURL_MODE:-copy}"  # copy|invalid|fail

touch "$called_file"

out=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    -o)
      out="${2:?missing output path after -o}"
      shift 2
      ;;
    --output)
      out="${2:?missing output path after --output}"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

if [ -z "${out:-}" ]; then
  echo "fake curl: missing -o/--output" >&2
  exit 2
fi

case "$mode" in
  copy)
    cp "$tarball_file" "$out"
    ;;
  invalid)
    printf "not-a-tarball" > "$out"
    ;;
  fail)
    exit 7
    ;;
  *)
    echo "fake curl: unsupported mode: $mode" >&2
    exit 2
    ;;
esac
EOF
chmod +x "$fake_bin/curl"

export PATH="$fake_bin:$PATH"
export FAKE_CURL_CALLED_FILE="$curl_called_file"
export FAKE_CURL_TARBALL_FILE="$fake_tarball_file"

make_tarball_with_top_dir() {
  local src_parent="$1"
  local top_dir_name="$2"
  local out_tarball="$3"

  mkdir -p "$src_parent/$top_dir_name"
  echo "hello" > "$src_parent/$top_dir_name/new.txt"
  tar -czf "$out_tarball" -C "$src_parent" "$top_dir_name"
}

make_tarball_without_top_dir() {
  local src_dir="$1"
  local out_tarball="$2"

  mkdir -p "$src_dir"
  echo "flat" > "$src_dir/flat.txt"
  tar -czf "$out_tarball" -C "$src_dir" "flat.txt"
}

reset_curl_called() {
  rm -f "$curl_called_file"
}

assert_curl_not_called() {
  if [ -f "$curl_called_file" ]; then
    echo "expected curl to not be called" >&2
    exit 1
  fi
}

assert_curl_called() {
  if [ ! -f "$curl_called_file" ]; then
    echo "expected curl to be called" >&2
    exit 1
  fi
}

echo "== fast path: .git present and sha matches (no curl) =="
reset_curl_called
export FAKE_CURL_MODE="copy"

ws_fast="$tmp_root/ws-fast"
mkdir -p "$ws_fast"
git -C "$ws_fast" init -q
git -C "$ws_fast" config user.email "test@example.com"
git -C "$ws_fast" config user.name "Test"
echo "keep" > "$ws_fast/keep.txt"
git -C "$ws_fast" add keep.txt
git -C "$ws_fast" commit -qm "init"
expected_sha_fast="$(git -C "$ws_fast" rev-parse HEAD)"

(cd "$tmp_root" && REPO="owner/repo" EXPECTED_SHA="$expected_sha_fast" WORKSPACE="$ws_fast" bash "$SCRIPT_UNDER_TEST" >/dev/null)

assert_curl_not_called
[ -f "$ws_fast/keep.txt" ] || {
  echo "expected workspace file to remain on fast path" >&2
  exit 1
}

echo "== tarball success: replace workspace contents =="
reset_curl_called
export FAKE_CURL_MODE="copy"

ws_ok="$tmp_root/ws-ok"
mkdir -p "$ws_ok"
echo "old" > "$ws_ok/old.txt"

tar_src_parent="$tmp_root/tar-src"
make_tarball_with_top_dir "$tar_src_parent" "repo-dir" "$fake_tarball_file"

(cd "$tmp_root" && REPO="owner/repo" EXPECTED_SHA="deadbeef" WORKSPACE="$ws_ok" bash "$SCRIPT_UNDER_TEST" >/dev/null)

assert_curl_called
[ ! -f "$ws_ok/old.txt" ] || {
  echo "expected old workspace file to be removed" >&2
  exit 1
}
[ -f "$ws_ok/new.txt" ] || {
  echo "expected tarball contents to be moved into workspace" >&2
  exit 1
}

echo "== invalid tarball: fails with clear error =="
reset_curl_called
export FAKE_CURL_MODE="invalid"

ws_invalid="$tmp_root/ws-invalid"
mkdir -p "$ws_invalid"

set +e
out_invalid="$(REPO="owner/repo" EXPECTED_SHA="deadbeef" WORKSPACE="$ws_invalid" bash "$SCRIPT_UNDER_TEST" 2>&1)"
code_invalid=$?
set -e

if [ "$code_invalid" -eq 0 ]; then
  echo "expected script to fail on invalid tarball" >&2
  echo "$out_invalid" >&2
  exit 1
fi
echo "$out_invalid" | grep -F "::error::tarball is invalid" >/dev/null || {
  echo "expected error message for invalid tarball" >&2
  echo "$out_invalid" >&2
  exit 1
}

echo "== missing src_dir: tarball has no top-level directory =="
reset_curl_called
export FAKE_CURL_MODE="copy"

ws_missing="$tmp_root/ws-missing"
mkdir -p "$ws_missing"

tar_src_flat="$tmp_root/tar-flat"
make_tarball_without_top_dir "$tar_src_flat" "$fake_tarball_file"

set +e
out_missing="$(REPO="owner/repo" EXPECTED_SHA="deadbeef" WORKSPACE="$ws_missing" bash "$SCRIPT_UNDER_TEST" 2>&1)"
code_missing=$?
set -e

if [ "$code_missing" -eq 0 ]; then
  echo "expected script to fail when tarball extracts without top-level dir" >&2
  echo "$out_missing" >&2
  exit 1
fi
echo "$out_missing" | grep -F "::error::Failed to locate extracted tarball directory" >/dev/null || {
  echo "expected missing src_dir error message" >&2
  echo "$out_missing" >&2
  exit 1
}

echo "OK: checkout_tarball.sh behaves as expected"

