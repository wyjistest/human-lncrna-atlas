#!/usr/bin/env python3
"""
verify_research_baselines.py

目的：
- 为 Phase 6.0 的 Research 产物提供一个“本地可选”的 baseline 校验入口。
- 通过 v2.3 sample DB（临时建库 + 导入 sample_data）生成候选输出，然后与
  `docs/baselines/research/` 下提交的 baseline 做逐文件 diff。

说明：
- 该校验会调用 bash 生成脚本：
  - scripts/research/generate_top_lncrna_target_genes_sample_baseline_local.sh
  - scripts/research/generate_disease_network_summary_sample_baseline_local.sh
- 这些脚本需要本机具备 `psql` 且当前用户有 CREATE/DROP DATABASE 权限。
- 默认不进入 CI 门禁（仅本地可选），避免 CI 环境差异/权限差异导致 flaky。
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _stable_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines(True)


def _normalize_markdown_artifact_paths(lines: list[str], artifact_files: Iterable[str]) -> list[str]:
    """
    Baseline Markdown 中经常会引用输出文件路径：
      - 在仓库内生成时会是 repo-relative（例如 docs/baselines/...）
      - 在 verify 脚本的临时目录生成时会是绝对路径（例如 /tmp/...）

    为避免“输出目录不同”导致的无意义 diff，这里将 markdown 中反引号包裹的路径
    统一归一化为文件名（仅针对本次 group 的 artifact 文件名）。
    """

    patterns: list[re.Pattern[str]] = []
    for rel in artifact_files:
        filename = Path(rel).name
        patterns.append(re.compile(rf"`[^`]*?({re.escape(filename)})`"))

    out: list[str] = []
    for line in lines:
        for pat in patterns:
            line = pat.sub(r"`\1`", line)
        out.append(line)
    return out


def _compare_text_files(expected: Path, actual: Path, *, group_artifacts: Iterable[str]) -> int:
    if expected.read_bytes() == actual.read_bytes():
        return 0

    expected_lines = _stable_lines(expected)
    actual_lines = _stable_lines(actual)

    if expected.suffix.lower() == ".md":
        expected_lines = _normalize_markdown_artifact_paths(expected_lines, group_artifacts)
        actual_lines = _normalize_markdown_artifact_paths(actual_lines, group_artifacts)
        if expected_lines == actual_lines:
            return 0

    diff = "".join(
        difflib.unified_diff(
            expected_lines,
            actual_lines,
            fromfile=str(expected),
            tofile=str(actual),
        )
    )
    print("ERROR: research baseline mismatch", file=sys.stderr)
    if diff:
        sys.stderr.write(diff)
    return 3


def _run_generator(
    *,
    repo_root: Path,
    script_path: Path,
    env: dict[str, str],
    label: str,
) -> int:
    cmd = ["bash", str(script_path)]
    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
    )
    if proc.returncode != 0:
        print(f"ERROR: generator failed: {label}", file=sys.stderr)
        if proc.stdout:
            sys.stderr.write(proc.stdout)
        return proc.returncode
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify research baselines (local optional; uses v2.3 sample DB).",
    )
    parser.add_argument(
        "--mode",
        choices=["local"],
        default="local",
        help="Verify mode (currently only local).",
    )
    parser.add_argument(
        "--only",
        choices=["all", "target-genes", "disease-network"],
        default="all",
        help="Only verify a subset (default: all).",
    )
    parser.add_argument(
        "--keep-tmp",
        action="store_true",
        help="Keep temporary output dir for debugging.",
    )
    return parser.parse_args(argv)


@dataclass(frozen=True)
class BaselineGroup:
    name: str
    generator_script: Path
    expected_files: tuple[str, ...]
    env_overrides: dict[str, str]


def _require_cmd(name: str) -> bool:
    return shutil.which(name) is not None


def _missing_baselines(baseline_dir: Path, expected_files: Iterable[str]) -> list[str]:
    missing: list[str] = []
    for rel in expected_files:
        if not (baseline_dir / rel).is_file():
            missing.append(rel)
    return missing


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = _repo_root()
    baseline_dir = repo_root / "docs" / "baselines" / "research"

    if not _require_cmd("bash"):
        print("ERROR: missing required command: bash", file=sys.stderr)
        return 1

    # 生成脚本内部会检查 psql/python3；此处先做一次快速提示，便于定位失败原因。
    if not _require_cmd("psql"):
        print("ERROR: missing required command: psql", file=sys.stderr)
        return 1
    if not _require_cmd("python3"):
        print("ERROR: missing required command: python3", file=sys.stderr)
        return 1

    groups: list[BaselineGroup] = [
        BaselineGroup(
            name="target-genes",
            generator_script=repo_root
            / "scripts"
            / "research"
            / "generate_top_lncrna_target_genes_sample_baseline_local.sh",
            expected_files=(
                "top-lncrna-target-genes-ba50-top50-species1.tsv",
                "top-lncrna-target-genes-ba50-top50-species1.txt",
                "top-lncrna-target-genes-ba50-top50-species1.md",
            ),
            env_overrides={
                "SPECIES_ID": "1",
                "MIN_BA": "50",
                "TOP_N": "50",
                "GENERATED_AT": "sample",
                "TARGET_PROTEIN_CODING_ONLY": "false",
            },
        ),
        BaselineGroup(
            name="disease-network",
            generator_script=repo_root
            / "scripts"
            / "research"
            / "generate_disease_network_summary_sample_baseline_local.sh",
            expected_files=(
                "disease-network-traits-evidence-1.tsv",
                "disease-network-lncrnas-evidence-1.tsv",
                "disease-network-summary-evidence-1.md",
            ),
            env_overrides={
                "EVIDENCE_SPECIES_ID": "1",
                "TOP_TRAITS": "50",
                "TOP_LNCRNAS": "50",
                "GENERATED_AT": "sample",
            },
        ),
    ]

    if args.only != "all":
        groups = [g for g in groups if g.name == args.only]

    if not baseline_dir.is_dir():
        print(f"ERROR: baseline dir not found: {baseline_dir}", file=sys.stderr)
        return 1

    for g in groups:
        if not g.generator_script.is_file():
            print(f"ERROR: generator script not found: {g.generator_script}", file=sys.stderr)
            return 1

        missing = _missing_baselines(baseline_dir, g.expected_files)
        if missing:
            print(f"ERROR: missing baseline files for {g.name}:", file=sys.stderr)
            for rel in missing:
                print(f"  - {baseline_dir / rel}", file=sys.stderr)
            print(
                "Hint: generate them via the corresponding scripts/research/generate_*_sample_baseline_local.sh",
                file=sys.stderr,
            )
            return 1

    if args.keep_tmp:
        tmp_root = Path(tempfile.mkdtemp(prefix="hla-research-baseline-"))
        tmp_ctx = None
    else:
        tmp_ctx = tempfile.TemporaryDirectory(prefix="hla-research-baseline-")
        tmp_root = Path(tmp_ctx.name)

    try:
        out_dir = tmp_root / "out"
        out_dir.mkdir(parents=True, exist_ok=True)

        for g in groups:
            env = os.environ.copy()
            env["OUT_DIR"] = str(out_dir)
            env.update(g.env_overrides)

            rc = _run_generator(
                repo_root=repo_root,
                script_path=g.generator_script,
                env=env,
                label=g.name,
            )
            if rc != 0:
                if args.keep_tmp:
                    print(f"[debug] tmp_dir kept: {tmp_root}", file=sys.stderr)
                return rc

            for rel in g.expected_files:
                expected = baseline_dir / rel
                actual = out_dir / rel
                if not actual.is_file():
                    print(f"ERROR: generator did not produce expected file: {actual}", file=sys.stderr)
                    if args.keep_tmp:
                        print(f"[debug] tmp_dir kept: {tmp_root}", file=sys.stderr)
                    return 1

                rc = _compare_text_files(expected, actual, group_artifacts=g.expected_files)
                if rc != 0:
                    if args.keep_tmp:
                        print(f"[debug] tmp_dir kept: {tmp_root}", file=sys.stderr)
                    return rc

        print("OK: research baselines match")
        if args.keep_tmp:
            print(f"[debug] tmp_dir kept: {tmp_root}")
        return 0
    finally:
        if tmp_ctx is not None:
            tmp_ctx.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
