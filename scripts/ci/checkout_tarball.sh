#!/usr/bin/env bash
set -euo pipefail

# Self-hosted / unstable-network checkout helper:
# - If workspace already has .git at EXPECTED_SHA: no-op (fast path)
# - Else: download GitHub tarball via API and replace workspace contents
#
# Inputs (env):
# - REPO         (default: GITHUB_REPOSITORY)
# - EXPECTED_SHA (default: GITHUB_SHA)
# - GH_TOKEN     (default: GITHUB_TOKEN; optional for public repos)
# - WORKSPACE    (default: GITHUB_WORKSPACE or pwd)

REPO="${REPO:-${GITHUB_REPOSITORY:-}}"
EXPECTED_SHA="${EXPECTED_SHA:-${GITHUB_SHA:-}}"
GH_TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
WORKSPACE="${WORKSPACE:-${GITHUB_WORKSPACE:-$(pwd)}}"
TARBALL_PATH="${TARBALL_PATH:-}"

if [ -z "${REPO:-}" ]; then
  echo "::error::REPO is required (e.g. owner/repo)" >&2
  exit 1
fi
if [ -z "${EXPECTED_SHA:-}" ]; then
  echo "::error::EXPECTED_SHA is required" >&2
  exit 1
fi
if [ -z "${WORKSPACE:-}" ] || [ "${WORKSPACE:-}" = "/" ]; then
  echo "::error::Refusing to operate on WORKSPACE='${WORKSPACE:-}'" >&2
  exit 1
fi
if [ ! -d "$WORKSPACE" ]; then
  echo "::error::WORKSPACE is not a directory: $WORKSPACE" >&2
  exit 1
fi

echo "::group::checkout precheck"
echo "repo=${REPO}"
echo "expected_sha=${EXPECTED_SHA}"
echo "workspace=${WORKSPACE}"
echo "token=${GH_TOKEN:+SET}${GH_TOKEN:-UNSET}"
echo "tarball_path=${TARBALL_PATH:-<unset>}"
echo "::endgroup::"

# Fast path: if workspace already contains the expected git commit, do nothing.
if [ -d "$WORKSPACE/.git" ]; then
  current_sha="$(cd "$WORKSPACE" && git rev-parse HEAD 2>/dev/null || true)"
  if [ -n "${current_sha:-}" ] && [ "$current_sha" = "$EXPECTED_SHA" ]; then
    echo "::notice::workspace already at expected sha (${EXPECTED_SHA}); skipping tarball checkout."
    exit 0
  fi
fi

tmp_dir="$(mktemp -d)"
cleanup() {
  if [ -n "${tmp_dir:-}" ] && [ -d "${tmp_dir:-}" ] && [ "${tmp_dir:-}" != "/" ]; then
    rm -rf "$tmp_dir"
  fi
}
trap cleanup EXIT

extract_dir="${tmp_dir}/extract"

tar_path=""
if [ -n "${TARBALL_PATH:-}" ]; then
  tar_path="$TARBALL_PATH"
else
  tar_path="${tmp_dir}/src.tar.gz"

  echo "::group::download tarball"
  echo "Downloading tarball for ${REPO}@${EXPECTED_SHA} ..."

  curl_args=(
    -fsSL
    --retry 5
    --retry-connrefused
    --retry-delay 2
    --connect-timeout 10
    --max-time 120
    -H "Accept: application/vnd.github+json"
  )
  if [ -n "${GH_TOKEN:-}" ]; then
    curl_args+=(-H "Authorization: Bearer ${GH_TOKEN}")
  fi

  curl "${curl_args[@]}" \
    "https://api.github.com/repos/${REPO}/tarball/${EXPECTED_SHA}" \
    -o "$tar_path"

  echo "::endgroup::"
fi

if [ ! -s "$tar_path" ]; then
  if [ -n "${TARBALL_PATH:-}" ]; then
    echo "::error::Provided tarball is missing or empty: ${tar_path}" >&2
  else
    echo "::error::Downloaded tarball is empty: ${tar_path}" >&2
  fi
  exit 1
fi

if ! tar -tzf "$tar_path" >/dev/null 2>&1; then
  echo "::error::tarball is invalid" >&2
  exit 1
fi

mkdir -p "$extract_dir"
tar -xzf "$tar_path" -C "$extract_dir"

src_dir="$(find "$extract_dir" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
if [ -z "${src_dir:-}" ] || [ ! -d "$src_dir" ]; then
  echo "::error::Failed to locate extracted tarball directory" >&2
  exit 1
fi

echo "::group::replace workspace"
echo "Workspace before:"
(cd "$WORKSPACE" && ls -la | head -n 200) || true

(cd "$WORKSPACE" && {
  shopt -s dotglob nullglob
  for item in *; do
    rm -rf -- "$item"
  done
  shopt -u dotglob nullglob
})

cp -a "${src_dir}/." "$WORKSPACE/"

echo "Workspace after:"
(cd "$WORKSPACE" && ls -la | head -n 200) || true
echo "::endgroup::"

echo "Checked out workspace from tarball."
