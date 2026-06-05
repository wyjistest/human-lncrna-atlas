#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 后端 Docker build 也会访问 PyPI 安装依赖。
# - Dockerfile 应支持可选 PIP_PROXY，避免受限网络中绕过本地代理。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
dockerfile="$REPO_ROOT/frontend/backend/Dockerfile"
compose_file="$REPO_ROOT/docker-compose.yml"
deployment_doc="$REPO_ROOT/docs/backend/DEPLOYMENT.md"

python3 - "$dockerfile" <<'PY'
import re
import sys
from pathlib import Path

dockerfile = Path(sys.argv[1])
text = dockerfile.read_text(encoding="utf-8")

if not re.search(r"^ARG PIP_PROXY=", text, flags=re.MULTILINE):
    raise SystemExit("backend Dockerfile must declare ARG PIP_PROXY")

if '--proxy "$PIP_PROXY"' not in text:
    raise SystemExit("backend Dockerfile pip install must pass --proxy when PIP_PROXY is set")

if "pip install -r requirements.txt -c constraints.txt" not in text:
    raise SystemExit("backend Dockerfile must keep installing locked backend requirements")
PY

python3 - "$compose_file" <<'PY'
import sys
from pathlib import Path

compose_file = Path(sys.argv[1])
text = compose_file.read_text(encoding="utf-8")

if "args:" not in text:
    raise SystemExit("docker-compose.yml backend build must declare build args")

if "PIP_PROXY: ${PIP_PROXY:-}" not in text:
    raise SystemExit("docker-compose.yml backend build must pass optional PIP_PROXY to Dockerfile")
PY

python3 - "$deployment_doc" <<'PY'
import sys
from pathlib import Path

deployment_doc = Path(sys.argv[1])
text = deployment_doc.read_text(encoding="utf-8")

if "COPY requirements.txt constraints.txt" not in text:
    raise SystemExit("deployment Dockerfile example must copy constraints.txt")

if "pip install -r requirements.txt -c constraints.txt" not in text:
    raise SystemExit("deployment Dockerfile example must install with constraints.txt")

if "RUN pip install --no-cache-dir -r requirements.txt" in text:
    raise SystemExit("deployment Dockerfile example must not install unconstrained requirements")
PY

echo "OK: backend Dockerfile pip install honors optional PIP_PROXY"
