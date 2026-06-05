#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import seaborn as sns
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter
from mpl_toolkits.axes_grid1.inset_locator import inset_axes


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = Path(__file__).resolve()

DEFAULT_SPECIES_ORDER = (
    {"species_code": "human", "display_name": "Human"},
    {"species_code": "chimp", "display_name": "Chimpanzee"},
    {"species_code": "macaque", "display_name": "Macaque"},
    {"species_code": "marmoset", "display_name": "Marmoset"},
)
DEFAULT_CELL_LINE_SUBSET = ["A549", "GM12878", "H1-hESC", "HepG2", "HMEC", "K562"]
PAPER_BASELINE_MARKS = [
    "H3K27me3",
    "H3K4me3",
    "H3K4me2",
    "H3K4me1",
    "H3K27ac",
    "H3K36me3",
    "H3K9ac",
    "H3K9me3",
    "DNase-HS",
]
FIG5_TRAIT_LABEL_MAP = {
    "obesity": "Obesity",
    "Abnormality of the nervous system": "nervous system",
    "Arteriosclerosis": "atherosclerosis",
    "Sclerosis of metaphyses of the upper limbs": "metaphyseal sclerosis",
}

sns.set_theme(style="whitegrid")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def display_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except Exception:
        return str(path)


def git_commit_sha(repo_root: Path, ref: str = "HEAD") -> str:
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", ref],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            .stdout.strip()
        )
    except Exception:
        return "unknown"


def read_tsv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except Exception:
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def shorten_gene_label(symbol: str | None) -> str:
    value = (symbol or "").strip()
    if not value:
        return "NA"
    if value.startswith("CATG"):
        base = value.split(".", 1)[0]
        digits = "".join(ch for ch in base if ch.isdigit())[-6:].zfill(6)
        return f"CATG{digits}"
    if value.startswith("ENSG"):
        base = value.split(".", 1)[0]
        digits = "".join(ch for ch in base if ch.isdigit())[-6:].zfill(6)
        return f"ENSG{digits}"
    if len(value) > 18:
        return value[:15] + "..."
    return value


def format_trait_display_label(trait_name: str) -> str:
    normalized = (trait_name or "").strip()
    return FIG5_TRAIT_LABEL_MAP.get(normalized, normalized)


def format_genomic_window_label(chromosome: str, start: int, end: int) -> str:
    return f"{chromosome}:{start / 1_000_000:.1f}-{end / 1_000_000:.1f} Mb"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate native single-canvas main-text Figures 2-5.")
    parser.add_argument("--repo-root", default=".", help="Repository root (default: current directory)")
    parser.add_argument("--panel-root", default="paper_figures", help="Directory containing generated TSV panel data")
    parser.add_argument("--out-dir", default="paper_figures/native", help="Output directory for native figures")
    parser.add_argument("--generated-at", default=None, help="Optional fixed UTC timestamp for metadata")
    parser.add_argument("--source-commit", default=None, help="Optional git ref to record as source_commit provenance")
    return parser.parse_args()


def save_figure(fig: plt.Figure, svg_path: Path, png_path: Path) -> None:
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(svg_path, bbox_inches="tight")
    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_metadata(
    *,
    figure_id: str,
    figure_number: int,
    title: str,
    repo_root: Path,
    generated_at: str,
    source_commit: str,
    inputs: Sequence[Path],
    svg_path: Path,
    png_path: Path,
    metadata_path: Path,
    panel_ids: Sequence[str],
) -> None:
    write_json(
        metadata_path,
        {
            "figure_id": figure_id,
            "figure_number": figure_number,
            "title": title,
            "script": display_path(SCRIPT_PATH, repo_root),
            "rendering_mode": "native_matplotlib_single_figure",
            "uses_panel_png_paste": False,
            "inputs": [display_path(path, repo_root) for path in inputs],
            "outputs": {
                "svg": display_path(svg_path, repo_root),
                "png": display_path(png_path, repo_root),
                "metadata": display_path(metadata_path, repo_root),
            },
            "panels": list(panel_ids),
            "notes": [
                "Native main figure rendered as one matplotlib figure.",
                "Panel data are read from frozen TSV exports; no panel PNG or SVG assets are pasted.",
            ],
            "generated_at": generated_at,
            "source_commit": source_commit,
        },
    )


def panel_label(ax: plt.Axes, letter: str, title: str) -> None:
    ax.text(
        -0.08,
        1.08,
        letter,
        transform=ax.transAxes,
        fontsize=13,
        fontweight="bold",
        va="top",
        ha="left",
        clip_on=False,
    )
    ax.set_title(title, loc="left", fontsize=10.5, fontweight="bold", pad=8)


def _cmap_color(cmap_name: str, value: float, vmin: float, vmax: float) -> Any:
    cmap = plt.get_cmap(cmap_name)
    if math.isclose(vmin, vmax):
        return cmap(0.5)
    return cmap(min(1.0, max(0.0, (value - vmin) / (vmax - vmin))))


def draw_vector_colorbar(
    ax: plt.Axes,
    cmap_name: str,
    vmin: float,
    vmax: float,
    label: str,
    *,
    ticks: Sequence[float] | None = None,
    position: tuple[float, float, float, float] = (1.025, 0.12, 0.025, 0.68),
    fontsize: float = 7.0,
    steps: int = 36,
) -> None:
    x0, y0, width, height = position
    for step in range(steps):
        frac0 = step / steps
        frac1 = (step + 1) / steps
        value = vmin + ((frac0 + frac1) / 2.0) * (vmax - vmin)
        ax.add_patch(
            Rectangle(
                (x0, y0 + frac0 * height),
                width,
                (frac1 - frac0) * height,
                transform=ax.transAxes,
                facecolor=_cmap_color(cmap_name, value, vmin, vmax),
                edgecolor="none",
                clip_on=False,
            ),
        )
    ax.add_patch(
        Rectangle(
            (x0, y0),
            width,
            height,
            transform=ax.transAxes,
            facecolor="none",
            edgecolor="#4A5568",
            linewidth=0.4,
            clip_on=False,
        ),
    )
    tick_values = list(ticks or [vmin, (vmin + vmax) / 2.0, vmax])
    for tick in tick_values:
        frac = 0.5 if math.isclose(vmin, vmax) else (tick - vmin) / (vmax - vmin)
        frac = min(1.0, max(0.0, frac))
        ax.plot(
            [x0 + width, x0 + width + 0.012],
            [y0 + frac * height, y0 + frac * height],
            transform=ax.transAxes,
            color="#4A5568",
            linewidth=0.5,
            clip_on=False,
        )
        if label.lower().endswith("fraction") or vmax <= 1.0:
            tick_label = f"{tick:.2f}".rstrip("0").rstrip(".")
        else:
            tick_label = f"{tick:.0f}" if abs(tick) >= 10 else f"{tick:.1f}"
        ax.text(
            x0 + width + 0.016,
            y0 + frac * height,
            tick_label,
            transform=ax.transAxes,
            fontsize=fontsize,
            va="center",
            ha="left",
            color="#263238",
            clip_on=False,
        )
    ax.text(
        x0 + width + 0.055,
        y0 + height / 2.0,
        label,
        transform=ax.transAxes,
        fontsize=fontsize + 0.5,
        rotation=90,
        va="center",
        ha="left",
        color="#263238",
        clip_on=False,
    )


def draw_horizontal_vector_colorbar(
    ax: plt.Axes,
    cmap_name: str,
    vmin: float,
    vmax: float,
    label: str,
    *,
    ticks: Sequence[float] | None = None,
    position: tuple[float, float, float, float] = (0.58, -0.26, 0.32, 0.035),
    fontsize: float = 6.2,
    steps: int = 36,
) -> None:
    x0, y0, width, height = position
    for step in range(steps):
        frac0 = step / steps
        frac1 = (step + 1) / steps
        value = vmin + ((frac0 + frac1) / 2.0) * (vmax - vmin)
        ax.add_patch(
            Rectangle(
                (x0 + frac0 * width, y0),
                (frac1 - frac0) * width,
                height,
                transform=ax.transAxes,
                facecolor=_cmap_color(cmap_name, value, vmin, vmax),
                edgecolor="none",
                clip_on=False,
            ),
        )
    ax.add_patch(
        Rectangle(
            (x0, y0),
            width,
            height,
            transform=ax.transAxes,
            facecolor="none",
            edgecolor="#4A5568",
            linewidth=0.4,
            clip_on=False,
        ),
    )
    tick_values = list(ticks or [vmin, (vmin + vmax) / 2.0, vmax])
    for tick in tick_values:
        frac = 0.5 if math.isclose(vmin, vmax) else (tick - vmin) / (vmax - vmin)
        frac = min(1.0, max(0.0, frac))
        ax.plot(
            [x0 + frac * width, x0 + frac * width],
            [y0, y0 - 0.018],
            transform=ax.transAxes,
            color="#4A5568",
            linewidth=0.5,
            clip_on=False,
        )
        tick_label = f"{tick:.2f}".rstrip("0").rstrip(".")
        ax.text(
            x0 + frac * width,
            y0 - 0.026,
            tick_label,
            transform=ax.transAxes,
            fontsize=fontsize,
            va="top",
            ha="center",
            color="#263238",
            clip_on=False,
        )
    ax.text(
        x0 - 0.012,
        y0 + height / 2.0,
        label,
        transform=ax.transAxes,
        fontsize=fontsize + 0.4,
        va="center",
        ha="right",
        color="#263238",
        clip_on=False,
    )


def draw_vector_heatmap(
    ax: plt.Axes,
    values: np.ndarray,
    *,
    xlabels: Sequence[str],
    ylabels: Sequence[str],
    cmap_name: str,
    vmin: float,
    vmax: float,
    annotations: np.ndarray | None = None,
    na_color: str = "#D9D9D9",
    x_rotation: float = 0.0,
    annot_fontsize: float = 6.5,
    tick_fontsize: float = 7.0,
    square: bool = False,
) -> None:
    nrows, ncols = values.shape
    for i in range(nrows):
        for j in range(ncols):
            value = float(values[i, j]) if np.isfinite(values[i, j]) else float("nan")
            facecolor = na_color if math.isnan(value) else _cmap_color(cmap_name, value, vmin, vmax)
            ax.add_patch(
                Rectangle(
                    (j, i),
                    1,
                    1,
                    facecolor=facecolor,
                    edgecolor="#F0F0F0",
                    linewidth=0.45,
                ),
            )
            if annotations is not None:
                label = str(annotations[i, j])
                if label:
                    normalized = 0.0 if math.isnan(value) or math.isclose(vmin, vmax) else (value - vmin) / (vmax - vmin)
                    text_color = "white" if normalized > 0.52 else "#263238"
                    ax.text(j + 0.5, i + 0.5, label, ha="center", va="center", fontsize=annot_fontsize, color=text_color)
    ax.set_xlim(0, ncols)
    ax.set_ylim(nrows, 0)
    ax.set_xticks(np.arange(ncols) + 0.5)
    ax.set_xticklabels(xlabels, rotation=x_rotation, ha="right" if x_rotation else "center", fontsize=tick_fontsize)
    ax.set_yticks(np.arange(nrows) + 0.5)
    ax.set_yticklabels(ylabels, fontsize=tick_fontsize)
    if square:
        ax.set_aspect("equal")
    for spine in ax.spines.values():
        spine.set_visible(False)


def render_fig2a(ax: plt.Axes, rows: Sequence[dict[str, str]], summary_rows: Sequence[dict[str, str]]) -> None:
    species_values: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        species_values[row["species_code"]].append(safe_float(row["binding_affinity"]))
    ordered_codes = [spec["species_code"] for spec in DEFAULT_SPECIES_ORDER]
    ordered_data = [species_values[code] for code in ordered_codes]
    ordered_names = [spec["display_name"] for spec in DEFAULT_SPECIES_ORDER]
    summary_by_code = {row["species_code"]: row for row in summary_rows}
    main_plot_ymax = max((safe_float(row.get("main_plot_ymax")) for row in summary_rows), default=200.0)
    full_plot_ymax = max((safe_float(row.get("full_plot_ymax")) for row in summary_rows), default=main_plot_ymax)
    palette = ["#0B3954", "#087E8B", "#BFD7EA", "#FF5A5F"]

    violin = ax.violinplot(ordered_data, showmeans=False, showmedians=False, showextrema=False)
    for body, color in zip(violin["bodies"], palette, strict=True):
        body.set_facecolor(color)
        body.set_edgecolor("#2B2B2B")
        body.set_alpha(0.72)
    box = ax.boxplot(ordered_data, widths=0.13, patch_artist=True, showfliers=False)
    for patch in box["boxes"]:
        patch.set_facecolor("#F7F5F2")
        patch.set_edgecolor("#2B2B2B")
    for median in box["medians"]:
        median.set_color("#C81D25")
        median.set_linewidth(1.4)
    ax.axhline(100.0, color="#C81D25", linestyle="--", linewidth=1.2)
    ax.set_xticks(range(1, len(ordered_names) + 1))
    ax.set_xticklabels(ordered_names, fontsize=8)
    ax.set_ylabel("Binding affinity", fontsize=9)
    ax.set_ylim(40, main_plot_ymax)
    for index, code in enumerate(ordered_codes, start=1):
        summary = summary_by_code.get(code, {})
        ax.text(index, 44.0, f">=100: {safe_float(summary.get('frac_ge_100')) * 100:.1f}%", ha="center", va="bottom", fontsize=7.4, color="#404040")
    ax.grid(axis="y", alpha=0.18)

    inset = inset_axes(ax, width="38%", height="34%", loc="upper left", borderpad=0.8)
    inset_violin = inset.violinplot(ordered_data, showmeans=False, showmedians=False, showextrema=False)
    for body, color in zip(inset_violin["bodies"], palette, strict=True):
        body.set_facecolor(color)
        body.set_edgecolor("#2B2B2B")
        body.set_alpha(0.55)
    inset.axhline(100.0, color="#C81D25", linestyle="--", linewidth=0.8)
    inset.set_ylim(0, max(full_plot_ymax, main_plot_ymax))
    inset.set_xticks([])
    inset.tick_params(axis="y", labelsize=7)
    inset.grid(axis="y", alpha=0.12)


def render_fig2b(ax: plt.Axes, rows: Sequence[dict[str, str]]) -> None:
    plot_rows = list(reversed(rows[:12]))
    y_positions = list(range(len(plot_rows)))
    species_color_map = {1: "#C81D25", 2: "#FF8C42", 3: "#087E8B", 4: "#0B3954"}
    for y_pos, row in zip(y_positions, plot_rows, strict=True):
        value = safe_int(row["unique_target_core_count"])
        species_count = safe_int(row["species_count"])
        ax.hlines(y=y_pos, xmin=0, xmax=value, color="#D7DCE2", linewidth=2.2)
        ax.plot(value, y_pos, "o", color=species_color_map.get(species_count, "#0B3954"), markersize=6.5)
    ax.set_yticks(y_positions)
    ax.set_yticklabels([row.get("display_label") or row.get("lncrna_core_id", "") for row in plot_rows], fontsize=7.5)
    ax.set_xlabel("Unique target-core count (BA >= 100)", fontsize=9)
    ax.text(
        0.0,
        -0.17,
        "Unadjusted breadth; not length/GC/repeat/motif normalized",
        transform=ax.transAxes,
        fontsize=7.4,
        color="#555555",
        va="top",
        ha="left",
        clip_on=False,
    )
    ax.grid(axis="x", alpha=0.18)
    ax.legend(
        handles=[
            Line2D([0], [0], marker="o", color="w", label=f"{count} species", markerfacecolor=color, markersize=6.5)
            for count, color in sorted(species_color_map.items())
        ],
        title="Species count",
        loc="lower right",
        fontsize=7,
        title_fontsize=7,
        frameon=False,
    )


def render_fig2c(ax: plt.Axes, rows: Sequence[dict[str, str]]) -> None:
    x = [safe_int(row["out_degree"]) for row in rows]
    y = [safe_float(row["eigenvector_centrality"]) for row in rows]
    max_support = max((safe_int(row["supporting_edge_count"]) for row in rows), default=1)
    sizes = [35 + 180 * (safe_int(row["supporting_edge_count"]) / max(max_support, 1)) for row in rows]
    colors = [safe_float(row["mean_outgoing_ba"]) for row in rows]
    color_min = min(colors) if colors else 0.0
    color_max = max(colors) if colors else 1.0
    point_colors = [_cmap_color("viridis", value, color_min, color_max) for value in colors]
    ax.scatter(x, y, s=sizes, c=point_colors, alpha=0.78, edgecolor="black", linewidth=0.25)
    top_labels = sorted(rows, key=lambda row: safe_float(row["eigenvector_centrality"]), reverse=True)[:5]
    for row in top_labels:
        label = shorten_gene_label(row.get("canonical_symbol") or row.get("human_ensembl_id"))
        x_value = safe_int(row["out_degree"])
        y_value = safe_float(row["eigenvector_centrality"])
        x_offset = -5 if x and x_value >= max(x) * 0.9 else 4
        ax.annotate(label, (x_value, y_value), textcoords="offset points", xytext=(x_offset, 4), fontsize=7, ha="right" if x_offset < 0 else "left")
    ax.set_xlabel("Unique target-core breadth", fontsize=9)
    ax.set_ylabel("Eigenvector centrality", fontsize=9)
    ax.set_xlim(-10, max(x) * 1.1 if x else 1.0)
    ax.grid(alpha=0.18)
    draw_vector_colorbar(ax, "viridis", color_min, color_max, "Mean outgoing BA", ticks=[100, 150, 200])


def node_key(node_row: dict[str, Any]) -> str:
    return f"{node_row['node_role']}:{safe_int(node_row['core_id'])}"


def hub_layout(node_rows: Sequence[dict[str, Any]]) -> dict[str, tuple[float, float]]:
    lnc_nodes = [row for row in node_rows if row["node_role"] == "lncrna"]
    target_nodes = [row for row in node_rows if row["node_role"] == "target"]
    positions: dict[str, tuple[float, float]] = {}
    if lnc_nodes:
        positions[node_key(lnc_nodes[0])] = (0.12, 0.5)
    ys = np.linspace(0.12, 0.88, len(target_nodes)) if target_nodes else []
    for y_pos, row in zip(ys, target_nodes, strict=True):
        positions[node_key(row)] = (0.68, float(y_pos))
    return positions


def community_layout(node_rows: Sequence[dict[str, Any]], edge_rows: Sequence[dict[str, Any]]) -> dict[str, tuple[float, float]]:
    graph = nx.Graph()
    for row in node_rows:
        graph.add_node(node_key(row))
    for row in edge_rows:
        graph.add_edge(f"lncrna:{safe_int(row['lncrna_core_id'])}", f"target:{safe_int(row['target_core_id'])}", weight=safe_float(row.get("mean_ba")))
    if not graph.nodes:
        return {}
    positions = nx.spring_layout(graph, seed=42, weight="weight")
    xs = [float(value[0]) for value in positions.values()]
    ys = [float(value[1]) for value in positions.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return {
        str(key): (
            0.1 + 0.8 * ((float(x_pos) - min_x) / (max_x - min_x or 1.0)),
            0.16 + 0.70 * ((float(y_pos) - min_y) / (max_y - min_y or 1.0)),
        )
        for key, (x_pos, y_pos) in positions.items()
    }


def draw_module_network(ax: plt.Axes, node_rows: Sequence[dict[str, Any]], edge_rows: Sequence[dict[str, Any]], layout: dict[str, tuple[float, float]], title: str) -> None:
    ax.text(0.0, 0.98, title, transform=ax.transAxes, fontsize=8.5, fontweight="bold", va="top")
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    max_ba = max((safe_float(row.get("max_ba") or row.get("mean_ba")) for row in edge_rows), default=1.0)
    for row in edge_rows:
        source = f"lncrna:{safe_int(row['lncrna_core_id'])}"
        target = f"target:{safe_int(row['target_core_id'])}"
        if source not in layout or target not in layout:
            continue
        x0, y0 = layout[source]
        x1, y1 = layout[target]
        ax.plot([x0, x1], [y0, y1], color="#999999", linewidth=0.8 + 2.4 * safe_float(row.get("max_ba") or row.get("mean_ba")) / max_ba, alpha=0.65, zorder=1)
    lnc_nodes = [row for row in node_rows if row["node_role"] == "lncrna"]
    target_nodes = [row for row in node_rows if row["node_role"] == "target"]
    if lnc_nodes:
        ax.scatter([layout[node_key(row)][0] for row in lnc_nodes], [layout[node_key(row)][1] for row in lnc_nodes], s=145, color="#C81D25", edgecolor="black", linewidth=0.6, zorder=3)
    if target_nodes:
        ax.scatter([layout[node_key(row)][0] for row in target_nodes], [layout[node_key(row)][1] for row in target_nodes], s=95, color="#BFD7EA", marker="s", edgecolor="black", linewidth=0.5, zorder=3)
    for row in node_rows:
        if node_key(row) not in layout:
            continue
        x_pos, y_pos = layout[node_key(row)]
        ax.text(x_pos + 0.022, y_pos, str(row["display_label"]), fontsize=6.2, va="center", ha="left")


def render_fig2d(ax: plt.Axes, panel_root: Path) -> None:
    ax.axis("off")
    sub = ax.get_subplotspec().subgridspec(2, 2, height_ratios=[0.16, 1.0], hspace=0.02, wspace=0.22)
    axes = [ax.figure.add_subplot(sub[1, 0]), ax.figure.add_subplot(sub[1, 1])]
    hub_nodes = read_tsv_rows(panel_root / "fig2/fig2D_hub_module_nodes.tsv")
    hub_edges = read_tsv_rows(panel_root / "fig2/fig2D_hub_module_edges.tsv")
    community_nodes = read_tsv_rows(panel_root / "fig2/fig2D_community_nodes.tsv")
    community_edges = read_tsv_rows(panel_root / "fig2/fig2D_community_edges.tsv")
    draw_module_network(axes[0], hub_nodes, hub_edges, hub_layout(hub_nodes), "Hub-centered")
    draw_module_network(axes[1], community_nodes, community_edges, community_layout(community_nodes, community_edges), "Modular community")


def render_figure2(panel_root: Path, out_dir: Path, repo_root: Path, generated_at: str, source_commit: str) -> None:
    inputs = [
        panel_root / "fig2/fig2A_ba_distribution.tsv",
        panel_root / "fig2/fig2A_summary.tsv",
        panel_root / "fig2/fig2B_hubs.tsv",
        panel_root / "fig2/fig2C_centrality.tsv",
        panel_root / "fig2/fig2D_hub_module_nodes.tsv",
        panel_root / "fig2/fig2D_hub_module_edges.tsv",
        panel_root / "fig2/fig2D_community_nodes.tsv",
        panel_root / "fig2/fig2D_community_edges.tsv",
    ]
    fig = plt.figure(figsize=(13.8, 9.4), constrained_layout=True)
    grid = fig.add_gridspec(2, 2, hspace=0.24, wspace=0.18)
    axes = [fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[0, 1]), fig.add_subplot(grid[1, 0]), fig.add_subplot(grid[1, 1])]
    render_fig2a(axes[0], read_tsv_rows(inputs[0]), read_tsv_rows(inputs[1]))
    panel_label(axes[0], "A", "Binding-affinity landscape")
    render_fig2b(axes[1], read_tsv_rows(inputs[2]))
    panel_label(axes[1], "B", "Unadjusted target-core breadth")
    render_fig2c(axes[2], read_tsv_rows(inputs[3]))
    panel_label(axes[2], "C", "Breadth versus centrality")
    panel_label(axes[3], "D", "Representative filtered subnetworks")
    render_fig2d(axes[3], panel_root)
    fig.suptitle("Figure 2. Global architecture of primate candidate lncRNA-gene networks", fontsize=15, fontweight="bold")
    write_native_outputs(fig, "figure2", 2, "Figure 2. Global architecture of primate candidate lncRNA–gene networks", out_dir, repo_root, generated_at, source_commit, inputs, ["fig2A", "fig2B", "fig2C", "fig2D"])


def render_fig3a(ax: plt.Axes, rows: Sequence[dict[str, str]]) -> None:
    sub = ax.get_subplotspec().subgridspec(2, 1, height_ratios=[3.0, 1.25], hspace=0.03)
    ax_bar = ax.figure.add_subplot(sub[0])
    ax_matrix = ax.figure.add_subplot(sub[1], sharex=ax_bar)
    ax.axis("off")
    x_positions = list(range(len(rows)))
    counts = [safe_int(row["count"]) for row in rows]
    color_by_species_count = {4: "#0B3954", 3: "#087E8B", 2: "#BFD7EA"}
    bar_colors = [color_by_species_count.get(safe_int(row["conservation_count"]), "#0B3954") for row in rows]
    ax_bar.bar(x_positions, counts, color=bar_colors)
    ax_bar.set_ylabel("Core-pair count", fontsize=8)
    ax_bar.grid(axis="y", alpha=0.18)
    ax_bar.tick_params(axis="x", labelbottom=False)
    species_codes = ["human", "chimp", "macaque", "marmoset"]
    y_positions = list(reversed(range(len(species_codes))))
    ax_matrix.set_yticks(y_positions)
    ax_matrix.set_yticklabels(["Human", "Chimp", "Macaque", "Marmoset"], fontsize=7.5)
    ax_matrix.set_ylim(-0.5, len(species_codes) - 0.5)
    ax_matrix.set_xlabel("Pattern", fontsize=8)
    ax_matrix.set_xticks(x_positions)
    ax_matrix.set_xticklabels([row["conservation_label"] for row in rows], fontsize=7.5)
    for x_pos, row in zip(x_positions, rows, strict=True):
        row_color = color_by_species_count.get(safe_int(row["conservation_count"]), "#0B3954")
        present_points: list[int] = []
        for y_pos, code in zip(y_positions, species_codes, strict=True):
            present = safe_int(row[code])
            ax_matrix.scatter(x_pos, y_pos, s=45, color=row_color if present else "#D0D0D0", zorder=3)
            if present:
                present_points.append(y_pos)
        if len(present_points) >= 2:
            ax_matrix.plot([x_pos, x_pos], [min(present_points), max(present_points)], color=row_color, linewidth=1.5)


def render_fig3b(ax: plt.Axes, rows: Sequence[dict[str, str]]) -> None:
    sub = ax.get_subplotspec().subgridspec(2, 2, height_ratios=[0.18, 1.0], hspace=0.02, wspace=0.16)
    axes = [ax.figure.add_subplot(sub[1, 0]), ax.figure.add_subplot(sub[1, 1])]
    ax.axis("off")
    y_limit = max((safe_float(row["proportion"]) for row in rows), default=1.0) * 1.15
    for subax, item_type, color in zip(axes, ["node", "edge"], ["#087E8B", "#C81D25"], strict=True):
        item_rows = [row for row in rows if row["item_type"] == item_type]
        xs = [safe_int(row["conservation_count"]) for row in item_rows]
        ys = [safe_float(row["proportion"]) for row in item_rows]
        subax.bar(xs, ys, color=color)
        subax.set_xticks(xs)
        subax.set_xlabel("Species", fontsize=8)
        subax.set_ylim(0, y_limit)
        subax.text(0.5, 0.96, item_type.capitalize(), transform=subax.transAxes, fontsize=8.5, ha="center", va="top")
        subax.grid(axis="y", alpha=0.18)
    axes[0].set_ylabel("Fraction within class", fontsize=8)


def render_fig3c(ax: plt.Axes, rows: Sequence[dict[str, str]]) -> None:
    species_codes = [spec["species_code"] for spec in DEFAULT_SPECIES_ORDER]
    species_labels = [spec["display_name"] for spec in DEFAULT_SPECIES_ORDER]
    def matrix_for(item_type: str) -> list[list[float]]:
        return [
            [
                safe_float(next(row for row in rows if row["item_type"] == item_type and row["species_a"] == species_a and row["species_b"] == species_b)["jaccard"])
                for species_b in species_codes
            ]
            for species_a in species_codes
        ]
    sub = ax.get_subplotspec().subgridspec(1, 2, wspace=0.24)
    axes = [ax.figure.add_subplot(sub[0, 0]), ax.figure.add_subplot(sub[0, 1])]
    ax.axis("off")
    mask = np.eye(len(species_codes), dtype=bool)
    for index, (subax, matrix, title) in enumerate(zip(axes, [matrix_for("node"), matrix_for("edge")], ["Node Jaccard", "Edge Jaccard"], strict=True)):
        matrix_array = np.array(matrix, dtype=float)
        matrix_array[mask] = np.nan
        annot = np.empty(matrix_array.shape, dtype=object)
        annot[:] = ""
        for row_idx in range(matrix_array.shape[0]):
            for col_idx in range(matrix_array.shape[1]):
                if np.isfinite(matrix_array[row_idx, col_idx]):
                    annot[row_idx, col_idx] = f"{matrix_array[row_idx, col_idx]:.2f}"
        draw_vector_heatmap(
            subax,
            matrix_array,
            xlabels=species_labels,
            ylabels=species_labels,
            cmap_name="Blues",
            vmin=0.0,
            vmax=1.0,
            annotations=annot,
            na_color="#FFFFFF",
            x_rotation=30,
            annot_fontsize=7,
            tick_fontsize=7,
            square=True,
        )
        if index == 1:
            subax.set_yticklabels([])
        subax.set_title(title, fontsize=8.5)


def draw_species_exemplar(ax: plt.Axes, species_code: str, species_name: str, node_rows: Sequence[dict[str, str]], edge_rows: Sequence[dict[str, str]]) -> None:
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.text(0.5, 1.02, species_name, transform=ax.transAxes, fontsize=7.2, fontweight="bold", ha="center", va="bottom")
    lnc_node = next((row for row in node_rows if row["node_role"] == "lncrna"), None)
    target_nodes = [row for row in node_rows if row["node_role"] == "target"]
    lnc_pos = (0.10, 0.5)
    ys = np.linspace(0.18, 0.82, max(len(target_nodes), 1))
    target_positions = {safe_int(row["core_id"]): (0.70, float(y_pos)) for row, y_pos in zip(target_nodes, ys, strict=True)}
    if lnc_node is not None:
        ax.scatter([lnc_pos[0]], [lnc_pos[1]], s=82, color="#C81D25", edgecolor="black", linewidth=0.4, zorder=3)
        ax.text(lnc_pos[0] + 0.035, lnc_pos[1], str(lnc_node["display_label"]), fontsize=5.4, va="center")
    for row in target_nodes:
        x_pos, y_pos = target_positions[safe_int(row["core_id"])]
        ax.scatter([x_pos], [y_pos], s=58, marker="s", color="#BFD7EA", edgecolor="black", linewidth=0.35, zorder=2)
        ax.text(x_pos + 0.025, y_pos, str(row["display_label"]), fontsize=5.3, va="center")
    edge_lookup = {safe_int(row["target_core_id"]): row for row in edge_rows if safe_int(row.get(species_code))}
    max_ba = max((safe_float(row.get("max_ba") or row.get("mean_ba")) for row in edge_lookup.values()), default=1.0)
    for target_core_id, row in edge_lookup.items():
        if target_core_id in target_positions:
            x_pos, y_pos = target_positions[target_core_id]
            ax.plot([lnc_pos[0], x_pos], [lnc_pos[1], y_pos], color="#C81D25", linewidth=0.8 + 1.9 * safe_float(row.get("max_ba") or row.get("mean_ba")) / max_ba, alpha=0.8, zorder=1)


def render_fig3d(ax: plt.Axes, panel_root: Path) -> None:
    sub = ax.get_subplotspec().subgridspec(3, 4, height_ratios=[0.18, 1.0, 1.0], hspace=0.46, wspace=0.18)
    ax.axis("off")
    conserved_nodes = read_tsv_rows(panel_root / "fig3/fig3D_conserved_nodes.tsv")
    conserved_edges = read_tsv_rows(panel_root / "fig3/fig3D_conserved_edges.tsv")
    rewired_nodes = read_tsv_rows(panel_root / "fig3/fig3D_rewired_nodes.tsv")
    rewired_edges = read_tsv_rows(panel_root / "fig3/fig3D_rewired_edges.tsv")
    for col, spec in enumerate(DEFAULT_SPECIES_ORDER):
        draw_species_exemplar(ax.figure.add_subplot(sub[1, col]), spec["species_code"], spec["display_name"], conserved_nodes, conserved_edges)
        draw_species_exemplar(ax.figure.add_subplot(sub[2, col]), spec["species_code"], spec["display_name"], rewired_nodes, rewired_edges)
    ax.text(-0.03, 0.80, "D1 conserved", transform=ax.transAxes, fontsize=7.6, fontweight="bold", ha="left", clip_on=False)
    ax.text(-0.03, 0.36, "D2 rewired", transform=ax.transAxes, fontsize=7.6, fontweight="bold", ha="left", clip_on=False)


def metric_value(rows: Sequence[dict[str, str]], metric: str) -> str:
    row = next((candidate for candidate in rows if candidate.get("metric") == metric), {})
    return str(row.get("value") or "0")


def render_fig3e(ax: plt.Axes, rows: Sequence[dict[str, str]]) -> None:
    observed = safe_float(metric_value(rows, "observed_four_species_shared_edges"))
    null_mean = safe_float(metric_value(rows, "target_permutation_null_mean"))
    target_p95 = safe_float(metric_value(rows, "target_permutation_null_p95"))
    degree_p95 = safe_float(metric_value(rows, "degree_bin_matched_p95"))
    down_median = safe_float(metric_value(rows, "marmoset_downsampling_observed_median"))
    down_range = metric_value(rows, "marmoset_downsampling_observed_p05_p95")
    down_null = safe_float(metric_value(rows, "marmoset_downsampling_null_p95"))
    sub = ax.get_subplotspec().subgridspec(2, 2, height_ratios=[0.20, 1.0], width_ratios=[1.35, 1.0], hspace=0.02, wspace=0.32)
    ax_main = ax.figure.add_subplot(sub[1, 0])
    ax_down = ax.figure.add_subplot(sub[1, 1])
    ax.axis("off")
    main_labels = ["Null mean", "Target p95", "Degree p95", "Observed"]
    main_values = [null_mean, target_p95, degree_p95, observed]
    ax_main.bar(range(4), main_values, color=["#D9D9D9", "#A6BDD7", "#74A9CF", "#D62728"], edgecolor="#4A5568", linewidth=0.6)
    ax_main.set_yscale("log")
    ax_main.set_ylabel("Edges (log scale)", fontsize=8)
    ax_main.set_xticks(range(4))
    ax_main.set_xticklabels(main_labels, rotation=18, ha="right", fontsize=7)
    ax_main.set_title("Main calibration", loc="left", fontsize=8.5, fontweight="bold")
    ax_main.text(0.02, 0.92, "8,799 vs 107/118", transform=ax_main.transAxes, fontsize=7, va="top")
    ax_down.bar([0, 1], [down_null, down_median], color=["#A6BDD7", "#D62728"], edgecolor="#4A5568", linewidth=0.6)
    ax_down.set_yscale("log")
    ax_down.set_xticks([0, 1])
    ax_down.set_xticklabels(["Null p95", "Observed"], fontsize=7)
    ax_down.set_title("Marmoset downsampling", loc="left", fontsize=8.5, fontweight="bold")
    ax_down.text(0.02, 0.92, f"median {int(down_median)}\np05-p95 {down_range}\nnull p95 {int(down_null)}", transform=ax_down.transAxes, fontsize=7, va="top")


def render_figure3(panel_root: Path, out_dir: Path, repo_root: Path, generated_at: str, source_commit: str) -> None:
    inputs = [
        panel_root / "fig3/fig3A_edge_upset.tsv",
        panel_root / "fig3/fig3B_node_vs_edge.tsv",
        panel_root / "fig3/fig3C_pairwise_sharing.tsv",
        panel_root / "fig3/fig3D_conserved_nodes.tsv",
        panel_root / "fig3/fig3D_conserved_edges.tsv",
        panel_root / "fig3/fig3D_rewired_nodes.tsv",
        panel_root / "fig3/fig3D_rewired_edges.tsv",
        panel_root / "fig3/fig3E_null_calibration.tsv",
    ]
    fig = plt.figure(figsize=(13.8, 13.2), constrained_layout=False)
    grid = fig.add_gridspec(
        3,
        2,
        height_ratios=[1.05, 1.06, 0.78],
        hspace=0.36,
        wspace=0.24,
        left=0.055,
        right=0.965,
        top=0.925,
        bottom=0.065,
    )
    axes = [
        fig.add_subplot(grid[0, 0]),
        fig.add_subplot(grid[0, 1]),
        fig.add_subplot(grid[1, 0]),
        fig.add_subplot(grid[1, 1]),
        fig.add_subplot(grid[2, :]),
    ]
    panel_label(axes[0], "A", "Edge-sharing strata")
    render_fig3a(axes[0], read_tsv_rows(inputs[0]))
    panel_label(axes[1], "B", "Node versus edge conservation")
    render_fig3b(axes[1], read_tsv_rows(inputs[1]))
    panel_label(axes[2], "C", "Pairwise node and edge sharing")
    render_fig3c(axes[2], read_tsv_rows(inputs[2]))
    panel_label(axes[3], "D", "Conserved and rewired examples")
    render_fig3d(axes[3], panel_root)
    panel_label(axes[4], "E", "Observed-vs-null calibration")
    render_fig3e(axes[4], read_tsv_rows(inputs[7]))
    fig.suptitle("Figure 3. Cross-species conservation and lineage-specific rewiring of candidate lncRNA-PCG edges", fontsize=15, fontweight="bold")
    write_native_outputs(fig, "figure3", 3, "Figure 3. Cross-species conservation and lineage-specific rewiring of candidate lncRNA–PCG edges", out_dir, repo_root, generated_at, source_commit, inputs, ["fig3A", "fig3B", "fig3C", "fig3D", "fig3E"])


def render_fig4a(ax: plt.Axes, rows: Sequence[dict[str, str]]) -> None:
    mark_order = [row["mark_name"] for row in rows if row["cell_line"] == DEFAULT_CELL_LINE_SUBSET[0]]
    cell_lines = DEFAULT_CELL_LINE_SUBSET
    values = np.full((len(mark_order), len(cell_lines)), np.nan)
    annot = np.empty((len(mark_order), len(cell_lines)), dtype=object)
    row_lookup = {(row["mark_name"], row["cell_line"]): row for row in rows}
    for i, mark_name in enumerate(mark_order):
        for j, cell_line in enumerate(cell_lines):
            row = row_lookup[(mark_name, cell_line)]
            if row["availability_status"] == "NA":
                annot[i, j] = "NA"
            else:
                values[i, j] = safe_float(row.get("overlap_fraction"))
                annot[i, j] = f"{100.0 * safe_float(row.get('overlap_fraction')):.1f}%"
    vmax = float(np.nanmax(values)) if np.isfinite(values).any() else 1.0
    draw_vector_heatmap(
        ax,
        values,
        xlabels=cell_lines,
        ylabels=mark_order,
        cmap_name="YlOrRd",
        vmin=0.0,
        vmax=vmax,
        annotations=annot,
        na_color="#D9D9D9",
        x_rotation=30,
        annot_fontsize=6.4,
        tick_fontsize=7,
    )
    ax.set_xlabel("Cell line", fontsize=8)
    ax.set_ylabel("Mark", fontsize=8)
    draw_horizontal_vector_colorbar(
        ax,
        "YlOrRd",
        0.0,
        vmax,
        "Overlap fraction",
        ticks=[0.0, round(vmax / 2.0, 2), round(vmax, 2)],
        position=(0.56, -0.24, 0.34, 0.032),
        fontsize=6.2,
    )


def render_fig4b(ax: plt.Axes, rows: Sequence[dict[str, str]]) -> None:
    cohorts = ["all_human_edges", "high_affinity"]
    colors = {"all_human_edges": "#0B3954", "high_affinity": "#C81D25"}
    sub = ax.get_subplotspec().subgridspec(2, 2, height_ratios=[0.18, 1.0], hspace=0.02, wspace=0.42)
    axes = [ax.figure.add_subplot(sub[1, 0]), ax.figure.add_subplot(sub[1, 1])]
    ax.axis("off")
    for subax, cohort in zip(axes, cohorts, strict=True):
        cohort_rows = [row for row in rows if row["cohort"] == cohort]
        labels = [row["display_label"] for row in reversed(cohort_rows)]
        fractions = [safe_float(row.get("fraction")) for row in reversed(cohort_rows)]
        subax.barh(labels, fractions, color=colors[cohort])
        subax.set_title("All edges" if cohort == "all_human_edges" else "BA >= 100", fontsize=8.5, pad=5)
        subax.set_xlabel("Fraction", fontsize=8)
        subax.set_xlim(0.0, max(fractions) * 1.12 if fractions else 1.0)
        subax.xaxis.set_major_formatter(FuncFormatter(lambda value, _pos: f"{value * 100:.0f}%"))
        subax.tick_params(axis="y", labelsize=6.4)
        subax.tick_params(axis="x", labelsize=7)


def render_fig4c(ax: plt.Axes, rows: Sequence[dict[str, str]]) -> None:
    class_order = ["bivalent_like", "active_like_non_bivalent", "other"]
    labels = ["Bivalent-like", "Active-like", "Other"]
    grouped = [[safe_float(row.get("binding_affinity")) for row in rows if row["context_class"] == key] for key in class_order]
    ax.boxplot(grouped, tick_labels=labels, patch_artist=True, boxprops={"facecolor": "#BFD7EA"})
    for index, values in enumerate(grouped, start=1):
        ax.text(index, max(values) * 1.02 if values else 0.5, f"n={len(values)}", ha="center", va="bottom", fontsize=7)
    ax.set_ylabel("Binding affinity", fontsize=8)
    ax.tick_params(axis="x", labelsize=7)


def render_fig4d(ax: plt.Axes, manifest_rows: Sequence[dict[str, str]], track_rows: Sequence[dict[str, str]]) -> None:
    sub = ax.get_subplotspec().subgridspec(len(manifest_rows) + 1, 1, height_ratios=[0.18] + [1.0] * len(manifest_rows), hspace=0.95)
    ax.axis("off")
    grouped_tracks: dict[tuple[int, str], list[dict[str, str]]] = defaultdict(list)
    for row in track_rows:
        grouped_tracks[(safe_int(row.get("regulation_id")), str(row.get("cell_line") or ""))].append(row)
    for idx, manifest in enumerate(manifest_rows):
        subax = ax.figure.add_subplot(sub[idx + 1, 0])
        key = (safe_int(manifest.get("regulation_id")), str(manifest.get("cell_line") or ""))
        rows = grouped_tracks.get(key, [])
        if not rows:
            subax.text(0.5, 0.5, "No overlap tracks", ha="center", va="center")
            subax.axis("off")
            continue
        mark_names = sorted({str(row.get("mark_name") or "") for row in rows})
        start = min(safe_int(row.get("peak_start")) for row in rows)
        end = max(safe_int(row.get("peak_end")) for row in rows)
        target_start = safe_int(manifest.get("target_start"), start)
        target_end = safe_int(manifest.get("target_end"), end)
        region_start = min(start, target_start)
        region_end = max(end, target_end)
        subax.add_patch(Rectangle((target_start, -0.3), max(1, target_end - target_start), len(mark_names) + 0.6, facecolor="#FDE68A", alpha=0.25, edgecolor="none"))
        for y_index, mark_name in enumerate(mark_names):
            for row in [item for item in rows if str(item.get("mark_name") or "") == mark_name]:
                subax.hlines(y=y_index, xmin=safe_int(row.get("peak_start")), xmax=safe_int(row.get("peak_end")), linewidth=4.2, color="#0B3954" if mark_name != "DNase-HS" else "#C81D25")
        subax.set_xlim(region_start, region_end)
        subax.set_ylim(-0.45, len(mark_names) - 0.05)
        subax.set_yticks(range(len(mark_names)))
        subax.set_yticklabels(mark_names, fontsize=7)
        subax.set_title(f"{manifest['exemplar_kind'].replace('_', ' ').title()}: {shorten_gene_label(manifest['lncrna_name'])} -> {shorten_gene_label(manifest['target_gene_name'])} ({manifest['cell_line']})", fontsize=7.8, pad=5)
        subax.xaxis.set_major_formatter(FuncFormatter(lambda value, _pos: f"{value / 1_000_000:.2f}"))
        subax.tick_params(axis="x", labelsize=6.5)
        subax.set_xlabel(format_genomic_window_label(str(manifest["target_chromosome"]), region_start, region_end), fontsize=7)


def render_figure4(panel_root: Path, out_dir: Path, repo_root: Path, generated_at: str, source_commit: str) -> None:
    inputs = [
        panel_root / "fig4/fig4A_overlap_summary.tsv",
        panel_root / "fig4/fig4B_mark_signatures.tsv",
        panel_root / "fig4/fig4C_bivalent_contrast.tsv",
        panel_root / "fig4/fig4D_igv_manifest.tsv",
        panel_root / "fig4/fig4D_overlap_tracks.tsv",
    ]
    fig = plt.figure(figsize=(13.8, 10.8), constrained_layout=False)
    grid = fig.add_gridspec(
        3,
        6,
        height_ratios=[0.14, 1.02, 1.0],
        width_ratios=[1, 1, 1, 0.92, 0.92, 0.92],
        hspace=0.50,
        wspace=0.95,
        left=0.075,
        right=0.95,
        top=0.89,
        bottom=0.09,
    )
    ax_header = fig.add_subplot(grid[0, :])
    ax_header.axis("off")
    ax_header.add_patch(Rectangle((0.0, 0.18), 1.0, 0.64, transform=ax_header.transAxes, facecolor="#EEF2F7", edgecolor="#CBD5E1", linewidth=0.8))
    ax_header.text(0.02, 0.52, "Main-text baseline: 8 core histone marks + DNase-HS | 56 experiments | 4,567,525 peaks", transform=ax_header.transAxes, fontsize=10, fontweight="bold", va="center")
    axes = [
        fig.add_subplot(grid[1, 0:3]),
        fig.add_subplot(grid[1, 3:6]),
        fig.add_subplot(grid[2, 0:3]),
        fig.add_subplot(grid[2, 3:6]),
    ]
    render_fig4a(axes[0], read_tsv_rows(inputs[0]))
    panel_label(axes[0], "A", "Histone-mark / DNase overlap")
    panel_label(axes[1], "B", "Mark-overlap context classes")
    render_fig4b(axes[1], read_tsv_rows(inputs[1]))
    render_fig4c(axes[2], read_tsv_rows(inputs[2]))
    panel_label(axes[2], "C", "Bivalent versus non-bivalent")
    panel_label(axes[3], "D", "Representative local tracks")
    render_fig4d(axes[3], read_tsv_rows(inputs[3]), read_tsv_rows(inputs[4]))
    fig.suptitle("Figure 4. Epigenomic context of candidate loci", fontsize=15, fontweight="bold")
    write_native_outputs(fig, "figure4", 4, "Figure 4. Epigenomic context of candidate loci", out_dir, repo_root, generated_at, source_commit, inputs, ["fig4A", "fig4B", "fig4C", "fig4D"])


def draw_tripartite(ax: plt.Axes, nodes: Sequence[dict[str, str]], edges: Sequence[dict[str, str]]) -> None:
    node_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for node in nodes:
        node_groups[str(node.get("node_type") or "other")].append(node)
    x_positions = {"trait": 0.0, "lncrna": 1.0, "gene": 2.18}
    positions: dict[str, tuple[float, float]] = {}
    for node_type, items in node_groups.items():
        y_values = np.linspace(0.84, 0.16, len(items)) if len(items) > 1 else np.array([0.5])
        for y, item in zip(y_values, items, strict=True):
            positions[str(item["node_id"])] = (x_positions.get(node_type, 1.5), float(y))
    max_reg_weight = max((safe_float(edge.get("weight")) for edge in edges if edge.get("edge_type") == "regulation"), default=1.0)
    for edge in edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source not in positions or target not in positions:
            continue
        if edge.get("edge_type") == "regulation":
            linewidth = 0.7 + 1.9 * safe_float(edge.get("weight")) / max(max_reg_weight, 1e-9)
            color, alpha = "#C81D25", 0.36
        else:
            linewidth, color, alpha = 1.1, "#7B8794", 0.72
        ax.plot([positions[source][0], positions[target][0]], [positions[source][1], positions[target][1]], color=color, linewidth=linewidth, alpha=alpha, zorder=1)
    palette = {"trait": "#D97706", "lncrna": "#C81D25", "gene": "#087E8B"}
    base_sizes = {"trait": 230.0, "lncrna": 120.0, "gene": 65.0}
    for node in nodes:
        node_id = str(node.get("node_id") or "")
        node_type = str(node.get("node_type") or "other")
        x, y = positions[node_id]
        size = base_sizes.get(node_type, 80.0) + 10.0 * math.sqrt(max(1.0, safe_float(node.get("value"))))
        ax.scatter([x], [y], s=size, color=palette.get(node_type, "#999999"), edgecolors="white", linewidth=0.9, zorder=2)
        label = str(node.get("display_label") or "")
        if node_type == "gene":
            ax.text(x + 0.07, y, label, ha="left", va="center", fontsize=6.8, color="#102A43")
        elif node_type == "trait":
            ax.text(x, y - 0.085, label, ha="center", va="top", fontsize=8, color="#7C2D12", fontweight="bold")
        else:
            ax.text(x - 0.07, y, label, ha="right", va="center", fontsize=6.8, color="#7C2D12", fontweight="bold", bbox={"boxstyle": "round,pad=0.12", "facecolor": "white", "edgecolor": "none", "alpha": 0.82})
    ax.set_xlim(-0.25, 2.55)
    ax.set_ylim(0.0, 1.0)
    ax.axis("off")


def render_fig5b(ax: plt.Axes, rows: Sequence[dict[str, str]]) -> None:
    heatmap = []
    row_labels = []
    for row in rows:
        rewiring_score = {"species_specific": 0, "rewired": 1, "conserved": 2}.get(str(row.get("rewiring_label")), 0)
        epigenomic_score = {"other": 0, "active_like": 1, "bivalent_like": 2, "active_like_non_bivalent": 1}.get(str(row.get("epigenomic_support_class")), 0)
        flagship_score = 1 if safe_bool(row.get("flagship_membership")) else 0
        heatmap.append([
            safe_float(row.get("trait_count")),
            safe_float(row.get("target_count")),
            safe_float(row.get("high_affinity_edge_count")),
            safe_float(row.get("mean_ba")),
            safe_float(row.get("max_ba")),
            safe_float(row.get("best_edge_conservation_count")),
            float(rewiring_score),
            float(epigenomic_score),
            float(flagship_score),
        ])
        row_labels.append(shorten_gene_label(str(row.get("lncrna_name") or "")))
    matrix = np.array(heatmap, dtype=float)
    normalized = np.zeros_like(matrix)
    for col_index in range(matrix.shape[1]):
        column = matrix[:, col_index]
        max_value = float(np.max(column)) if len(column) else 0.0
        min_value = float(np.min(column)) if len(column) else 0.0
        normalized[:, col_index] = 0.0 if math.isclose(max_value, min_value) else (column - min_value) / (max_value - min_value)
    draw_vector_heatmap(
        ax,
        normalized,
        xlabels=["Traits", "Targets", "BA>=100", "Mean BA", "Max BA", "Conserv.", "Rewiring", "Epigen.", "Flagship"],
        ylabels=row_labels,
        cmap_name="YlGnBu",
        vmin=0.0,
        vmax=1.0,
        x_rotation=35,
        tick_fontsize=6.7,
    )
    ax.set_xlabel("")
    ax.set_ylabel("")
    draw_vector_colorbar(ax, "YlGnBu", 0.0, 1.0, "Column-normalized", ticks=[0.0, 0.5, 1.0], position=(1.02, 0.12, 0.022, 0.72), fontsize=7)
    ax.text(0.0, -0.20, "Column-normalized visualization only; not effect size", transform=ax.transAxes, fontsize=7.2, color="#555555", ha="left", va="top", clip_on=False)


def render_fig5c(ax: plt.Axes, rows: Sequence[dict[str, str]]) -> None:
    ordered_trait_names = list(dict.fromkeys(row["trait_name"] for row in rows))
    lnc_labels = list(dict.fromkeys(row["display_label"] for row in rows))
    y_index = {label: idx for idx, label in enumerate(lnc_labels)}
    x_index = {name: idx for idx, name in enumerate(ordered_trait_names)}
    xs, ys, sizes, colors = [], [], [], []
    for row in rows:
        xs.append(x_index[row["trait_name"]])
        ys.append(y_index[row["display_label"]])
        sizes.append(28 + 13 * math.sqrt(max(1, safe_int(row.get("target_count")))))
        colors.append(safe_float(row.get("mean_ba")))
    color_min = min(colors) if colors else 0.0
    color_max = max(colors) if colors else 1.0
    point_colors = [_cmap_color("OrRd", value, color_min, color_max) for value in colors]
    ax.scatter(xs, ys, s=sizes, c=point_colors, alpha=0.68, edgecolors="#334E68", linewidth=0.3)
    ax.set_xticks(range(len(ordered_trait_names)))
    ax.set_xticklabels([format_trait_display_label(name) for name in ordered_trait_names], rotation=20, ha="right", fontsize=7)
    ax.set_yticks(range(len(lnc_labels)))
    ax.set_yticklabels(lnc_labels, fontsize=7)
    ax.set_xlabel("Trait", fontsize=8)
    ax.set_ylabel("Candidate lncRNA", fontsize=8)
    ax.grid(axis="x", alpha=0.14)
    ax.grid(axis="y", alpha=0.08)
    draw_vector_colorbar(ax, "OrRd", color_min, color_max, "Mean BA", ticks=[60, 85, 110], position=(1.035, 0.12, 0.026, 0.70), fontsize=7)


def render_fig5d(ax: plt.Axes, manifest: dict[str, str], nodes: Sequence[dict[str, str]], edges: Sequence[dict[str, str]]) -> None:
    sub = ax.get_subplotspec().subgridspec(2, 2, height_ratios=[0.18, 1.0], width_ratios=[1.16, 1.24], hspace=0.02, wspace=0.14)
    ax_network = ax.figure.add_subplot(sub[1, 0])
    ax_text = ax.figure.add_subplot(sub[1, 1])
    ax.axis("off")
    draw_tripartite(ax_network, nodes, edges)
    ax_text.axis("off")
    lines = [
        ("Trait", format_trait_display_label(manifest.get("trait_name", ""))),
        ("Candidate lncRNA", manifest.get("lncrna_name", "")),
        ("Displayed targets", manifest.get("candidate_targets", "")),
        ("High-affinity edges", manifest.get("high_affinity_edges", "")),
        ("BA range", manifest.get("ba_range", "")),
        ("Edge class", f"{manifest.get('rewiring_label', '').replace('_', '-')}, {manifest.get('best_edge_conservation_count', '')}-species"),
        ("Epigenomic", manifest.get("epigenomic_support_class", "").replace("_", "-")),
        ("Lit.-backed targets", f"{manifest.get('flagship_targets_with_trait_literature_support', '')}/{manifest.get('candidate_targets', '')}"),
    ]
    ax_text.text(0.0, 0.98, "Evidence card", fontsize=9.5, fontweight="bold", va="top")
    y = 0.86
    for key, value in lines:
        ax_text.text(0.0, y, key, fontsize=7.2, fontweight="bold", color="#334E68", va="top")
        ax_text.text(0.58, y, str(value), fontsize=7.2, color="#102A43", va="top")
        y -= 0.095


def render_figure5(panel_root: Path, out_dir: Path, repo_root: Path, generated_at: str, source_commit: str) -> None:
    inputs = [
        panel_root / "fig5/fig5A_tripartite_nodes.tsv",
        panel_root / "fig5/fig5A_tripartite_edges.tsv",
        panel_root / "fig5/fig5B_ranking_matrix.tsv",
        panel_root / "fig5/fig5C_trait_specificity.tsv",
        panel_root / "fig5/fig5D_case_manifest.tsv",
        panel_root / "fig5/fig5D_case_nodes.tsv",
        panel_root / "fig5/fig5D_case_edges.tsv",
    ]
    fig = plt.figure(figsize=(13.8, 9.7), constrained_layout=False)
    grid = fig.add_gridspec(
        2,
        2,
        height_ratios=[0.94, 1.06],
        hspace=0.34,
        wspace=0.26,
        left=0.07,
        right=0.95,
        top=0.92,
        bottom=0.08,
    )
    axes = [fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[0, 1]), fig.add_subplot(grid[1, 0]), fig.add_subplot(grid[1, 1])]
    draw_tripartite(axes[0], read_tsv_rows(inputs[0]), read_tsv_rows(inputs[1]))
    panel_label(axes[0], "A", "Flagship trait-lncRNA-PCG network")
    render_fig5b(axes[1], read_tsv_rows(inputs[2]))
    panel_label(axes[1], "B", "Integrated candidate ranking")
    render_fig5c(axes[2], read_tsv_rows(inputs[3]))
    panel_label(axes[2], "C", "Shared versus trait-specific candidates")
    manifest_rows = read_tsv_rows(inputs[4])
    render_fig5d(axes[3], manifest_rows[0] if manifest_rows else {}, read_tsv_rows(inputs[5]), read_tsv_rows(inputs[6]))
    panel_label(axes[3], "D", "Focused flagship case")
    fig.suptitle("Figure 5. Trait-centered prioritization of candidate lncRNAs", fontsize=15, fontweight="bold")
    write_native_outputs(fig, "figure5", 5, "Figure 5. Trait-centered prioritization of candidate lncRNAs", out_dir, repo_root, generated_at, source_commit, inputs, ["fig5A", "fig5B", "fig5C", "fig5D"])


def write_native_outputs(
    fig: plt.Figure,
    figure_id: str,
    figure_number: int,
    title: str,
    out_dir: Path,
    repo_root: Path,
    generated_at: str,
    source_commit: str,
    inputs: Sequence[Path],
    panel_ids: Sequence[str],
) -> None:
    svg_path = out_dir / f"{figure_id}_native.svg"
    png_path = out_dir / f"{figure_id}_native.png"
    metadata_path = out_dir / f"{figure_id}_native.metadata.json"
    save_figure(fig, svg_path, png_path)
    write_metadata(
        figure_id=figure_id,
        figure_number=figure_number,
        title=title,
        repo_root=repo_root,
        generated_at=generated_at,
        source_commit=source_commit,
        inputs=inputs,
        svg_path=svg_path,
        png_path=png_path,
        metadata_path=metadata_path,
        panel_ids=panel_ids,
    )


def render_native_main_figures(repo_root: Path, panel_root: Path, out_dir: Path, generated_at: str, source_commit: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    render_figure2(panel_root, out_dir, repo_root, generated_at, source_commit)
    render_figure3(panel_root, out_dir, repo_root, generated_at, source_commit)
    render_figure4(panel_root, out_dir, repo_root, generated_at, source_commit)
    render_figure5(panel_root, out_dir, repo_root, generated_at, source_commit)


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    panel_root = (repo_root / args.panel_root).resolve()
    out_dir = (repo_root / args.out_dir).resolve()
    generated_at = args.generated_at or utc_now_iso()
    source_commit_ref = str(args.source_commit or "HEAD").strip() or "HEAD"
    source_commit = git_commit_sha(repo_root, source_commit_ref)
    if args.source_commit and source_commit == "unknown":
        raise RuntimeError(f"Unable to resolve --source-commit {args.source_commit!r} via git rev-parse")
    render_native_main_figures(repo_root, panel_root, out_dir, generated_at, source_commit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
