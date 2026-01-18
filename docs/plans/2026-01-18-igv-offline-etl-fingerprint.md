# IGV Offline Assets + ETL Input Fingerprint Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** 扩展 IGV 离线资源脚本支持多物种基因组（panTro5/rheMac10/calJac3），并为 ETL 提供“输入文件指纹/可选校验（checksum/size/line-count）”的通用工具与最小测试闭环。

**Architecture:** 在 `scripts/genomes/download_hg19_igv_assets.sh` 基础上保持向后兼容（默认 hg19），新增 `--assembly` 等参数以复用同一套校验/manifest 逻辑；ETL 侧新增 `etl/file_checks.py` 提供标准库实现的指纹与校验函数，并以小型 pytest 用例覆盖。

**Tech Stack:** Bash（脚本与自测）、Python 3（标准库 hashlib/gzip）、pytest（单元测试）。

---

### Task 1: 建立 Bash 行为测试（TDD - RED）

**Files:**
- Create: `scripts/genomes/tests/test_download_igv_assets.sh`

**Step 1: Write the failing test**
- 目标行为：`download_hg19_igv_assets.sh --assembly panTro5 --write-manifest <dir>` 能在文件已存在时跳过下载并通过校验，且写出 `panTro5_igv_assets.manifest.tsv`。

**Step 2: Run test to verify it fails**
- Run: `bash scripts/genomes/tests/test_download_igv_assets.sh`
- Expected: FAIL（当前脚本不支持 `--assembly` / manifest 文件名不匹配 / 2bit 最小尺寸过大等）

---

### Task 2: 实现多物种离线下载（TDD - GREEN）

**Files:**
- Modify: `scripts/genomes/download_hg19_igv_assets.sh`
- Modify: `README.md`
- (Optional) Modify: `docs/HG19_OFFLINE_ASSETS.md`

**Step 1: Minimal implementation**
- 增加 `--assembly <name>`（默认 `hg19`）与 `--alias-url <url>`（可选）
- 下载/文件名从 `hg19.*` 泛化为 `${assembly}.*`
- SHA256 环境变量从硬编码 `HG19_*` 泛化为 `${ASSEMBLY_PREFIX}_*`（例如 `PANTRO5_CHROMSIZES_SHA256`）
- 2bit 最小尺寸：hg19 保持 100MB，其他 assembly 使用更保守阈值（例如 1MB，可通过 env 覆盖）
- alias 表下载：默认按 IGV data 仓库路径尝试下载（404 则告警并跳过）
- manifest：默认写入 `${assembly}_igv_assets.manifest.tsv`

**Step 2: Run tests**
- Run: `bash scripts/genomes/tests/test_download_igv_assets.sh`
- Expected: PASS

---

### Task 3: 建立 ETL 文件指纹/校验的 Python 单测（TDD - RED）

**Files:**
- Create: `etl/tests/test_file_checks.py`

**Step 1: Write the failing test**
- 覆盖：sha256 计算、行数统计（plain/gz）、最小 bytes、行数范围、sha mismatch 失败。

**Step 2: Run test to verify it fails**
- Run: `python3 -m pytest -q etl/tests/test_file_checks.py`
- Expected: FAIL（模块不存在）

---

### Task 4: 实现 ETL 文件指纹模块（TDD - GREEN）

**Files:**
- Create: `etl/file_checks.py`

**Step 1: Minimal implementation**
- `sha256_hex_file(path)`
- `count_lines(path, gz: bool | None = None)`
- `validate_file(path, min_bytes=0, min_lines=0, max_lines=0, expected_sha256=None, gz=None)`

**Step 2: Run tests**
- Run: `python3 -m pytest -q etl/tests/test_file_checks.py`
- Expected: PASS

---

### Task 5: 对齐本地与 GitHub Actions（快速回归）

**Files:**
- Modify: `scripts/run-tests.sh`（新增 `etl-checks` 并纳入 `ci`）
- Modify: `.github/workflows/test.yml`（在 Backend Checks job 中新增一步跑 `etl/tests`，保持无 DB 依赖）

**Step 1: Verify locally**
- Run: `./scripts/run-tests.sh ci`
- Expected: PASS

---

### Task 6: 提交与推送（小步可回滚）

**Step 1: Commit**
- `git add ...`
- `git commit -m "feat: add ETL input fingerprint checks"`

**Step 2: Push + watch**
- `git push`
- `gh run list --limit 5`
- `gh run watch <id> --exit-status`

