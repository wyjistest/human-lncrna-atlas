#!/usr/bin/env python3
"""Batch compute `gene_peak_associations` for all active experiments.

目标（与仓库约束对齐）：
- **可审计**：按 experiment 输出处理/跳过原因与统计汇总
- **可回滚**：仅做 INSERT（`ON CONFLICT DO NOTHING`），如需回滚可按 experiment_id 删除
- **防混组装**：默认只处理 reference_genome 匹配期望组装（默认 hg19）的 experiments

典型用法：

```bash
cd <repo-root>/frontend/backend

# 先 dry-run 看看会处理哪些 experiment
python3 scripts/compute_gene_peak_associations.py --dry-run

# 真正执行（默认跳过已存在 associations 的 experiment），并在末尾刷新物化视图
python3 scripts/compute_gene_peak_associations.py

# 如需强制重跑（即使已存在部分 associations；依赖 ON CONFLICT 防重复）
python3 scripts/compute_gene_peak_associations.py --force
```
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import psycopg2


logger = logging.getLogger(__name__)


# 让本脚本在 pytest/importlib 加载时也能 import 同目录脚本（import_chipseq.py）
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from import_chipseq import ChIPSeqImporter  # noqa: E402


@dataclass(frozen=True)
class ActiveExperiment:
    experiment_id: int
    species_id: int
    experiment_name: str
    reference_genome: Optional[str]


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="批量为所有 active experiments 生成 gene_peak_associations（可审计/可回滚）",
    )

    parser.add_argument(
        "--db-host",
        default=os.environ.get("DB_HOST", "localhost"),
        help="数据库地址（默认读取 env DB_HOST；fallback localhost）",
    )
    parser.add_argument(
        "--db-port",
        type=int,
        default=_env_int("DB_PORT", 5432),
        help="数据库端口（默认读取 env DB_PORT；fallback 5432）",
    )
    parser.add_argument(
        "--db-name",
        default=os.environ.get("DB_NAME", "lncrna_production"),
        help="数据库名（默认读取 env DB_NAME；fallback lncrna_production）",
    )
    parser.add_argument(
        "--db-user",
        default=os.environ.get("DB_USER", "postgres"),
        help="数据库用户（默认读取 env DB_USER；fallback postgres）",
    )
    parser.add_argument(
        "--db-password",
        default=os.environ.get("DB_PASSWORD", ""),
        help="数据库密码（默认读取 env DB_PASSWORD；fallback 空）",
    )

    parser.add_argument(
        "--expected-reference-genome",
        default=os.environ.get("EXPECTED_REFERENCE_GENOME", "hg19"),
        help="只处理 reference_genome 匹配该值的 experiments（默认 hg19）",
    )
    parser.add_argument(
        "--require-reference-genome",
        action="store_true",
        help="若 reference_genome 为空/NULL，则跳过（默认允许 NULL 并继续）",
    )

    parser.add_argument(
        "--associations-flanking",
        type=int,
        default=10000,
        help="计算 associations 的 flanking 窗口（bp；默认 10000）",
    )
    parser.add_argument(
        "--associations-promoter-window",
        type=int,
        default=2000,
        help="promoter 判定窗口（bp；默认 2000）",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="仅处理前 N 个 active experiments（默认 0 表示不限制）",
    )

    parser.add_argument(
        "--report-jsonl",
        default="",
        help="将执行过程追加写入 JSONL 报告文件（可选；适合长跑审计/排障）",
    )
    parser.add_argument(
        "--resume-from",
        default="",
        help="从已有 JSONL 报告恢复：跳过已处理 experiments（可选；断点续跑）",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="某个 experiment 失败时继续处理下一个（默认失败即中止）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅输出将要处理的 experiments（不写入数据库）",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="即使该 experiment 已存在 associations 也强制执行（依赖 ON CONFLICT 防重复）",
    )

    parser.add_argument(
        "--refresh-mvs",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="结束后刷新 chipseq 相关物化视图（默认 true，可用 --no-refresh-mvs 关闭）",
    )

    parser.add_argument("--verbose", action="store_true", help="打印更详细日志")

    return parser.parse_args(argv)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_jsonl(path: str, record: dict) -> None:
    if not path:
        return

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, sort_keys=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()


def _load_resume_done_experiment_ids(path: str) -> set[int]:
    if not path:
        return set()

    p = Path(path)
    if not p.exists():
        return set()

    done_statuses = {
        "computed",
        "skipped_existing",
        "skipped_reference_mismatch",
        "skipped_reference_unknown",
        "skipped_resume",
    }

    done: set[int] = set()
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not isinstance(obj, dict):
            continue

        status = obj.get("status")
        exp_id = obj.get("experiment_id")
        if status in done_statuses and isinstance(exp_id, int):
            done.add(exp_id)

    return done


def _normalize_ref_genome(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def reference_genome_matches(reference_genome: Optional[str], expected: str) -> bool:
    value = _normalize_ref_genome(reference_genome)
    if not value:
        return False

    exp = _normalize_ref_genome(expected)
    if not exp:
        return False

    # 常见别名：GRCh37/hg19, GRCh38/hg38
    if exp in {"hg19", "grch37"}:
        return ("hg19" in value) or ("grch37" in value)
    if exp in {"hg38", "grch38"}:
        return ("hg38" in value) or ("grch38" in value)

    return value == exp


def has_gene_peak_associations_table(conn) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'gene_peak_associations'
            )
            """
        )
        return bool(cur.fetchone()[0])


def fetch_active_experiments(conn) -> list[ActiveExperiment]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              experiment_id,
              species_id,
              experiment_name,
              reference_genome
            FROM chipseq_experiments
            WHERE is_active = TRUE
            ORDER BY species_id, experiment_id
            """
        )
        rows = cur.fetchall()

    experiments: list[ActiveExperiment] = []
    for row in rows:
        exp_id, species_id, name, ref = row
        experiments.append(
            ActiveExperiment(
                experiment_id=int(exp_id),
                species_id=int(species_id),
                experiment_name=str(name),
                reference_genome=(str(ref) if ref is not None and str(ref).strip() else None),
            )
        )
    return experiments


def experiment_has_any_associations(conn, experiment_id: int) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM gene_peak_associations WHERE experiment_id = %s LIMIT 1",
            (experiment_id,),
        )
        return cur.fetchone() is not None


def compute_gene_peak_associations_for_experiment(
    conn,
    experiment_id: int,
    species_id: int,
    *,
    flanking: int,
    promoter_window: int,
) -> int:
    importer = ChIPSeqImporter(db_config={})
    importer.conn = conn
    return importer.compute_gene_peak_associations(
        experiment_id=experiment_id,
        species_id=species_id,
        flanking=flanking,
        promoter_window=promoter_window,
    )


def refresh_chipseq_materialized_views(conn) -> None:
    importer = ChIPSeqImporter(db_config={})
    importer.conn = conn
    importer.refresh_materialized_views()


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    db_config = {
        "host": args.db_host,
        "port": args.db_port,
        "dbname": args.db_name,
        "user": args.db_user,
        "password": args.db_password,
    }

    conn = psycopg2.connect(**db_config)
    conn.autocommit = False

    processed = 0
    skipped_existing = 0
    skipped_resume = 0
    skipped_reference_mismatch = 0
    skipped_reference_unknown = 0
    errors = 0
    inserted_total = 0
    refresh_called = 0

    report_jsonl = args.report_jsonl
    if args.resume_from and not report_jsonl:
        report_jsonl = args.resume_from
    resume_done = _load_resume_done_experiment_ids(args.resume_from)
    run_started_at = _utc_now_iso()
    _write_jsonl(
        report_jsonl,
        {
            "status": "run_start",
            "started_at": run_started_at,
            "expected_reference_genome": args.expected_reference_genome,
            "require_reference_genome": bool(args.require_reference_genome),
            "force": bool(args.force),
            "refresh_mvs": bool(args.refresh_mvs),
            "associations_flanking": int(args.associations_flanking),
            "associations_promoter_window": int(args.associations_promoter_window),
            "resume_from": args.resume_from or None,
        },
    )

    try:
        if not has_gene_peak_associations_table(conn):
            logger.error(
                "gene_peak_associations 表不存在；请先应用 chipseq schema（frontend/backend/sql/chipseq_schema.sql）。"
            )
            return 1

        experiments = fetch_active_experiments(conn)
        if args.limit and args.limit > 0:
            experiments = experiments[: args.limit]

        if not experiments:
            logger.info("未找到 active chipseq_experiments（is_active=TRUE）。")
            return 0

        expected = args.expected_reference_genome
        for exp in experiments:
            exp_started = time.time()
            if exp.reference_genome:
                if not reference_genome_matches(exp.reference_genome, expected):
                    logger.warning(
                        "Skip experiment_id=%s name=%s: reference_genome=%s (expected=%s)",
                        exp.experiment_id,
                        exp.experiment_name,
                        exp.reference_genome,
                        expected,
                    )
                    skipped_reference_mismatch += 1
                    _write_jsonl(
                        report_jsonl,
                        {
                            "status": "skipped_reference_mismatch",
                            "experiment_id": exp.experiment_id,
                            "species_id": exp.species_id,
                            "experiment_name": exp.experiment_name,
                            "reference_genome": exp.reference_genome,
                            "expected_reference_genome": expected,
                            "duration_ms": int((time.time() - exp_started) * 1000),
                        },
                    )
                    continue
            else:
                if args.require_reference_genome:
                    logger.warning(
                        "Skip experiment_id=%s name=%s: reference_genome is NULL",
                        exp.experiment_id,
                        exp.experiment_name,
                    )
                    skipped_reference_unknown += 1
                    _write_jsonl(
                        report_jsonl,
                        {
                            "status": "skipped_reference_unknown",
                            "experiment_id": exp.experiment_id,
                            "species_id": exp.species_id,
                            "experiment_name": exp.experiment_name,
                            "reference_genome": None,
                            "expected_reference_genome": expected,
                            "duration_ms": int((time.time() - exp_started) * 1000),
                        },
                    )
                    continue

            if (not args.force) and exp.experiment_id in resume_done:
                logger.info(
                    "Skip experiment_id=%s name=%s: already processed in resume report",
                    exp.experiment_id,
                    exp.experiment_name,
                )
                skipped_resume += 1
                _write_jsonl(
                    report_jsonl,
                    {
                        "status": "skipped_resume",
                        "experiment_id": exp.experiment_id,
                        "species_id": exp.species_id,
                        "experiment_name": exp.experiment_name,
                        "reference_genome": exp.reference_genome,
                        "duration_ms": int((time.time() - exp_started) * 1000),
                    },
                )
                continue

            if not args.force and experiment_has_any_associations(conn, exp.experiment_id):
                logger.info(
                    "Skip experiment_id=%s name=%s: gene_peak_associations already exists",
                    exp.experiment_id,
                    exp.experiment_name,
                )
                skipped_existing += 1
                _write_jsonl(
                    report_jsonl,
                    {
                        "status": "skipped_existing",
                        "experiment_id": exp.experiment_id,
                        "species_id": exp.species_id,
                        "experiment_name": exp.experiment_name,
                        "reference_genome": exp.reference_genome,
                        "duration_ms": int((time.time() - exp_started) * 1000),
                    },
                )
                continue

            if args.dry_run:
                logger.info(
                    "[dry-run] Would compute associations: experiment_id=%s name=%s",
                    exp.experiment_id,
                    exp.experiment_name,
                )
                _write_jsonl(
                    report_jsonl,
                    {
                        "status": "dry_run",
                        "experiment_id": exp.experiment_id,
                        "species_id": exp.species_id,
                        "experiment_name": exp.experiment_name,
                        "reference_genome": exp.reference_genome,
                        "duration_ms": int((time.time() - exp_started) * 1000),
                    },
                )
                continue

            try:
                inserted = compute_gene_peak_associations_for_experiment(
                    conn,
                    exp.experiment_id,
                    exp.species_id,
                    flanking=args.associations_flanking,
                    promoter_window=args.associations_promoter_window,
                )
                conn.commit()
                processed += 1
                inserted_total += int(inserted)
                _write_jsonl(
                    report_jsonl,
                    {
                        "status": "computed",
                        "experiment_id": exp.experiment_id,
                        "species_id": exp.species_id,
                        "experiment_name": exp.experiment_name,
                        "reference_genome": exp.reference_genome,
                        "inserted": int(inserted),
                        "duration_ms": int((time.time() - exp_started) * 1000),
                    },
                )
            except Exception as exc:
                conn.rollback()
                errors += 1
                _write_jsonl(
                    report_jsonl,
                    {
                        "status": "error",
                        "experiment_id": exp.experiment_id,
                        "species_id": exp.species_id,
                        "experiment_name": exp.experiment_name,
                        "reference_genome": exp.reference_genome,
                        "error": str(exc),
                        "duration_ms": int((time.time() - exp_started) * 1000),
                    },
                )
                if not args.continue_on_error:
                    raise
                logger.exception(
                    "Compute associations failed; continue_on_error enabled (experiment_id=%s name=%s)",
                    exp.experiment_id,
                    exp.experiment_name,
                )

        if (not args.dry_run) and args.refresh_mvs:
            refresh_chipseq_materialized_views(conn)
            conn.commit()
            refresh_called += 1
            _write_jsonl(
                report_jsonl,
                {
                    "status": "refresh_mvs",
                    "refreshed": True,
                },
            )

        finished_at = _utc_now_iso()
        _write_jsonl(
            report_jsonl,
            {
                "status": "run_end",
                "started_at": run_started_at,
                "finished_at": finished_at,
                "processed": processed,
                "inserted_total": inserted_total,
                "skipped_existing": skipped_existing,
                "skipped_resume": skipped_resume,
                "skipped_reference_mismatch": skipped_reference_mismatch,
                "skipped_reference_unknown": skipped_reference_unknown,
                "errors": errors,
                "refreshed_mvs": refresh_called,
            },
        )

        logger.info(
            "Summary: processed=%s inserted_total=%s skipped_existing=%s skipped_resume=%s skipped_ref_mismatch=%s skipped_ref_unknown=%s errors=%s refreshed_mvs=%s",
            processed,
            inserted_total,
            skipped_existing,
            skipped_resume,
            skipped_reference_mismatch,
            skipped_reference_unknown,
            errors,
            refresh_called,
        )
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
