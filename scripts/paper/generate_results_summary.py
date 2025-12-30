#!/usr/bin/env python3
"""
Generate a lightweight, dependency-free results summary for the paper draft.

This script only reads the pre-generated CSV outputs under `notebooks/results/`
and writes a Markdown summary under `docs/paper/results_summary.md`.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class InputPaths:
    top100_csv: Path
    network_nodes_csv: Path
    network_edges_csv: Path


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _safe_int(value: str) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _safe_float(value: str) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def summarize_top100(rows: Iterable[dict[str, str]]) -> str:
    rows = list(rows)
    if not rows:
        return "No rows found.\n"

    species_counts = Counter(r.get("species_name", "") for r in rows)
    top1 = rows[0]

    target_counts = [_safe_int(r.get("target_count", "")) for r in rows]
    target_counts = [x for x in target_counts if x is not None]

    avg_ba = [_safe_float(r.get("avg_ba", "")) for r in rows]
    avg_ba = [x for x in avg_ba if x is not None]

    lines: list[str] = []
    lines.append("### Top-100 high-affinity lncRNAs (from `top_100_high_affinity_lncrnas.csv`)")
    lines.append("")
    lines.append(f"- Entries: {len(rows)}")
    lines.append(f"- Species distribution: {dict(species_counts)}")
    lines.append(
        "- #1 entry: "
        f"{top1.get('lncrna_name')} ({top1.get('species_name')}), "
        f"targets={top1.get('target_count')}, avg_ba={top1.get('avg_ba')}, max_ba={top1.get('max_ba')}"
    )
    if target_counts:
        lines.append(f"- target_count: min={min(target_counts)}, median={sorted(target_counts)[len(target_counts)//2]}, max={max(target_counts)}")
    if avg_ba:
        lines.append(f"- avg_ba: min={min(avg_ba):.3f}, max={max(avg_ba):.3f}")
    lines.append("")
    return "\n".join(lines) + "\n"


def summarize_network(nodes: Iterable[dict[str, str]], edges: Iterable[dict[str, str]]) -> str:
    nodes = list(nodes)
    edges = list(edges)

    lines: list[str] = []
    lines.append("### Derived subnetwork (from `network_nodes.csv` / `network_edges.csv`)")
    lines.append("")
    lines.append(f"- Nodes: {len(nodes)}")
    lines.append(f"- Edges: {len(edges)}")

    if nodes:
        if "node_type" in nodes[0]:
            node_type_counts = Counter(n.get("node_type", "") for n in nodes)
            lines.append(f"- Node types: {dict(node_type_counts)}")
        if "species" in nodes[0]:
            species_counts = Counter(n.get("species", "") for n in nodes)
            lines.append(f"- Node species: {dict(species_counts)}")

        # Top nodes by degree (if present)
        if "degree" in nodes[0]:
            parsed: list[tuple[int, dict[str, str]]] = []
            for n in nodes:
                degree = _safe_int(n.get("degree", ""))
                if degree is None:
                    continue
                parsed.append((degree, n))
            parsed.sort(key=lambda x: x[0], reverse=True)
            topk = parsed[:5]
            if topk:
                lines.append("- Top nodes by degree (top 5):")
                for degree, n in topk:
                    lines.append(
                        f"  - {n.get('node_id')} ({n.get('node_type')}, {n.get('species')}): degree={degree}"
                    )

    lines.append("")
    return "\n".join(lines) + "\n"


def build_markdown(paths: InputPaths) -> str:
    sections: list[str] = []
    sections.append("# Results Summary (Auto-generated)")
    sections.append("")
    sections.append("This file is generated from precomputed notebook outputs (CSV only).")
    sections.append("")

    if paths.top100_csv.exists():
        sections.append(summarize_top100(read_csv_rows(paths.top100_csv)).rstrip())
    else:
        sections.append(f"### Missing: `{paths.top100_csv}`")
        sections.append("")

    if paths.network_nodes_csv.exists() and paths.network_edges_csv.exists():
        sections.append(
            summarize_network(
                read_csv_rows(paths.network_nodes_csv),
                read_csv_rows(paths.network_edges_csv),
            ).rstrip()
        )
    else:
        if not paths.network_nodes_csv.exists():
            sections.append(f"### Missing: `{paths.network_nodes_csv}`")
            sections.append("")
        if not paths.network_edges_csv.exists():
            sections.append(f"### Missing: `{paths.network_edges_csv}`")
            sections.append("")

    sections.append("---")
    sections.append("")
    sections.append("## Notes")
    sections.append("")
    sections.append("- For publication-quality figures, see `notebooks/figures/`.")
    sections.append("- To regenerate notebook outputs, follow `notebooks/README.md`.")
    sections.append("")

    return "\n".join(sections).strip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root (default: current directory)",
    )
    parser.add_argument(
        "--out",
        default="docs/paper/results_summary.md",
        help="Output markdown path (default: docs/paper/results_summary.md)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    out_path = (repo_root / args.out).resolve()

    paths = InputPaths(
        top100_csv=repo_root / "notebooks/results/top_100_high_affinity_lncrnas.csv",
        network_nodes_csv=repo_root / "notebooks/results/network_nodes.csv",
        network_edges_csv=repo_root / "notebooks/results/network_edges.csv",
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_markdown(paths), encoding="utf-8")
    print(f"Wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

