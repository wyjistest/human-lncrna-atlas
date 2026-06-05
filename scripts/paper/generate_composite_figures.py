#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import textwrap
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

import matplotlib


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = Path(__file__).resolve()

CANVAS_WIDTH = 2200
OUTER_MARGIN = 72
TITLE_BLOCK_HEIGHT = 108
TITLE_GAP = 24
ROW_GAP = 48
COLUMN_GAP = 36
PANEL_LABEL_HEIGHT = 38
PANEL_LABEL_GAP = 12
HEADER_STRIP_HEIGHT = 96
BACKGROUND_COLOR = "#ffffff"
PANEL_BORDER_COLOR = "#d9e2ec"
HEADER_STRIP_FILL = "#eef2f7"
HEADER_STRIP_BORDER = "#cbd5e1"
TITLE_COLOR = "#102a43"
SUBTITLE_COLOR = "#486581"
PANEL_LABEL_COLOR = "#102a43"
PANEL_BADGE_FILL = "#d9e2ec"
PANEL_BADGE_TEXT = "#102a43"

PANEL_ROOT_DEFAULT = "paper_figures"
OUT_DIR_DEFAULT = "paper_figures/composites"

TITLE_FONT = Path(matplotlib.get_data_path()) / "fonts/ttf/DejaVuSans-Bold.ttf"
BODY_FONT = Path(matplotlib.get_data_path()) / "fonts/ttf/DejaVuSans.ttf"
TITLE_WRAP_WIDTH = 82
TITLE_LINE_HEIGHT = 44


DEFAULT_FIGURES: list[dict[str, Any]] = [
    {
        "figure_number": 1,
        "figure_id": "figure1",
        "title": "Figure 1. From trait catalogs to orthology-aware candidate lncRNA–PCG edges",
        "rows": [
            {
                "kind": "panel_row",
                "panels": [
                    {"panel_id": "fig1A", "letter": "A", "title": "Catalog gap: nodes, not edges", "rel_svg": "fig1/fig1A_catalog_gap.svg"},
                    {"panel_id": "fig1B", "letter": "B", "title": "Ortholog mapping across four primates", "rel_svg": "fig1/fig1B_ortholog_mapping.svg"},
                ],
            },
            {
                "kind": "panel_row",
                "panels": [
                    {"panel_id": "fig1C", "letter": "C", "title": "Orthology-aware triplex workflow", "rel_svg": "fig1/fig1C_workflow.svg"},
                ],
            },
            {
                "kind": "panel_row",
                "panels": [
                    {"panel_id": "fig1D", "letter": "D", "title": "Frozen submission snapshot", "rel_svg": "fig1/fig1D_kpi.svg"},
                ],
            },
        ],
    },
    {
        "figure_number": 2,
        "figure_id": "figure2",
        "title": "Figure 2. Global architecture of primate candidate lncRNA–gene networks",
        "rows": [
            {
                "kind": "panel_row",
                "panels": [
                    {"panel_id": "fig2A", "letter": "A", "title": "Binding-affinity landscape", "rel_svg": "fig2/fig2A_ba_distribution.svg"},
                    {"panel_id": "fig2B", "letter": "B", "title": "Unadjusted target-core breadth prioritization", "rel_svg": "fig2/fig2B_hubs.svg"},
                ],
            },
            {
                "kind": "panel_row",
                "panels": [
                    {"panel_id": "fig2C", "letter": "C", "title": "Hub breadth versus eigenvector centrality", "rel_svg": "fig2/fig2C_centrality.svg"},
                    {"panel_id": "fig2D", "letter": "D", "title": "Representative filtered subnetworks", "rel_svg": "fig2/fig2D_readable_subnetworks.svg"},
                ],
            },
        ],
    },
    {
        "figure_number": 3,
        "figure_id": "figure3",
        "title": "Figure 3. Cross-species conservation and lineage-specific rewiring of candidate lncRNA–PCG edges",
        "rows": [
            {
                "kind": "panel_row",
                "panels": [
                    {"panel_id": "fig3A", "letter": "A", "title": "Conserved-edge strata across 2 to 4 species", "rel_svg": "fig3/fig3A_edge_upset.svg"},
                    {"panel_id": "fig3B", "letter": "B", "title": "Node conservation versus edge conservation", "rel_svg": "fig3/fig3B_node_vs_edge.svg"},
                ],
            },
            {
                "kind": "panel_row",
                "panels": [
                    {"panel_id": "fig3C", "letter": "C", "title": "Species-pair node and edge sharing", "rel_svg": "fig3/fig3C_pairwise_sharing.svg"},
                    {"panel_id": "fig3D", "letter": "D", "title": "Illustrative conserved and rewired candidate examples", "rel_svg": "fig3/fig3D_examples.svg"},
                ],
            },
            {
                "kind": "panel_row",
                "panels": [
                    {"panel_id": "fig3E", "letter": "E", "title": "Observed-vs-null calibration", "rel_svg": "fig3/fig3E_null_calibration.svg"},
                ],
            },
        ],
    },
    {
        "figure_number": 4,
        "figure_id": "figure4",
        "title": "Figure 4. Epigenomic context of candidate loci",
        "rows": [
            {
                "kind": "header_strip",
                "lines": [
                    "Main-text baseline: 8 core histone marks + DNase-HS | 56 experiments | 4,567,525 peaks",
                    "Cross-mark subset: A549 | GM12878 | H1-hESC | HepG2 | HMEC | K562",
                ],
            },
            {
                "kind": "panel_row",
                "panels": [
                    {"panel_id": "fig4A", "letter": "A", "title": "Histone-mark / DNase overlap summary", "rel_svg": "fig4/fig4A_overlap_summary.svg"},
                    {"panel_id": "fig4B", "letter": "B", "title": "Mark-overlap context classes", "rel_svg": "fig4/fig4B_mark_signatures.svg"},
                ],
            },
            {
                "kind": "panel_row",
                "panels": [
                    {"panel_id": "fig4C", "letter": "C", "title": "Bivalent versus non-bivalent contrast", "rel_svg": "fig4/fig4C_bivalent_contrast.svg"},
                    {"panel_id": "fig4D", "letter": "D", "title": "Representative local epigenomic tracks", "rel_svg": "fig4/fig4D_igv_snapshots.svg"},
                ],
            },
        ],
    },
    {
        "figure_number": 5,
        "figure_id": "figure5",
        "title": "Figure 5. Trait-centered prioritization of candidate lncRNAs",
        "rows": [
            {
                "kind": "panel_row",
                "panels": [
                    {"panel_id": "fig5A", "letter": "A", "title": "Simplified flagship trait–lncRNA–PCG subnetwork", "rel_svg": "fig5/fig5A_tripartite_network.svg"},
                    {"panel_id": "fig5B", "letter": "B", "title": "Integrated candidate lncRNA ranking matrix", "rel_svg": "fig5/fig5B_ranking_matrix.svg"},
                ],
            },
            {
                "kind": "panel_row",
                "panels": [
                    {"panel_id": "fig5C", "letter": "C", "title": "Shared versus trait-specific regulators", "rel_svg": "fig5/fig5C_trait_specificity.svg"},
                    {"panel_id": "fig5D", "letter": "D", "title": "Focused flagship case study", "rel_svg": "fig5/fig5D_case_study.svg"},
                ],
            },
        ],
    },
]


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compose paper-facing Figure 1-5 composites from existing panel assets.")
    parser.add_argument("--repo-root", default=".", help="Repository root (default: current directory)")
    parser.add_argument(
        "--panel-root",
        default=PANEL_ROOT_DEFAULT,
        help=f"Directory containing existing panel assets (default: {PANEL_ROOT_DEFAULT})",
    )
    parser.add_argument(
        "--out-dir",
        default=OUT_DIR_DEFAULT,
        help=f"Output directory for composite figures (default: {OUT_DIR_DEFAULT})",
    )
    parser.add_argument(
        "--generated-at",
        default=None,
        help="Optional fixed UTC timestamp for metadata (default: now)",
    )
    parser.add_argument(
        "--source-commit",
        default=None,
        help="Optional git ref to record as source_commit provenance (default: HEAD)",
    )
    return parser.parse_args()


def load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


def wrap_title(title: str) -> list[str]:
    return textwrap.wrap(title, width=TITLE_WRAP_WIDTH, break_long_words=False) or [title]


def parse_svg_size(svg_path: Path) -> tuple[float, float]:
    root = ET.parse(svg_path).getroot()
    width = root.attrib.get("width")
    height = root.attrib.get("height")
    view_box = root.attrib.get("viewBox")
    if view_box:
        parts = [float(value) for value in view_box.replace(",", " ").split()]
        if len(parts) == 4 and parts[2] > 0 and parts[3] > 0:
            return parts[2], parts[3]
    if width and height:
        def _clean(value: str) -> float:
            cleaned = value.strip().lower().replace("pt", "").replace("px", "")
            return float(cleaned)
        return _clean(width), _clean(height)
    raise ValueError(f"unable to determine SVG size for {svg_path}")


def with_generation_provenance(payload: dict[str, Any], *, generated_at: str, source_commit: str) -> dict[str, Any]:
    output = dict(payload)
    output["generated_at"] = generated_at
    output["source_commit"] = source_commit
    output.pop("release_commit", None)
    return output


def build_default_figure_specs(repo_root: Path, panel_root: Path | None = None) -> list[dict[str, Any]]:
    resolved_panel_root = (panel_root or (repo_root / PANEL_ROOT_DEFAULT)).resolve()
    specs: list[dict[str, Any]] = []
    for figure in DEFAULT_FIGURES:
        figure_spec = {
            "figure_number": figure["figure_number"],
            "figure_id": figure["figure_id"],
            "title": figure["title"],
            "rows": [],
        }
        for row in figure["rows"]:
            if row["kind"] == "header_strip":
                figure_spec["rows"].append({
                    "kind": "header_strip",
                    "lines": list(row["lines"]),
                })
                continue
            panels: list[dict[str, Any]] = []
            for panel in row["panels"]:
                svg_path = resolved_panel_root / panel["rel_svg"]
                panels.append(
                    {
                        "panel_id": panel["panel_id"],
                        "letter": panel["letter"],
                        "title": panel["title"],
                        "svg_path": svg_path,
                        "png_path": svg_path.with_suffix(".png"),
                    }
                )
            figure_spec["rows"].append({"kind": "panel_row", "panels": panels})
        specs.append(figure_spec)
    return specs


def ensure_panel_assets(figure_specs: list[dict[str, Any]]) -> None:
    missing: list[str] = []
    for figure in figure_specs:
        for row in figure["rows"]:
            for panel in row.get("panels", []):
                for path in (panel["svg_path"], panel["png_path"]):
                    if not Path(path).exists():
                        missing.append(str(path))
    if missing:
        preview = "\n".join(missing[:10])
        raise FileNotFoundError(f"missing composite panel assets:\n{preview}")


def resolve_panel_dimensions(figure_specs: list[dict[str, Any]]) -> None:
    for figure in figure_specs:
        for row in figure["rows"]:
            for panel in row.get("panels", []):
                width, height = parse_svg_size(Path(panel["svg_path"]))
                panel["source_width"] = width
                panel["source_height"] = height
                panel["aspect_ratio"] = width / height if height else 1.0


def measure_layout(figure_spec: dict[str, Any]) -> dict[str, Any]:
    content_width = CANVAS_WIDTH - 2 * OUTER_MARGIN
    title_lines = wrap_title(str(figure_spec["title"]))
    title_block_height = max(TITLE_BLOCK_HEIGHT, 30 + TITLE_LINE_HEIGHT * len(title_lines))
    y_cursor = OUTER_MARGIN + title_block_height + TITLE_GAP
    layout_rows: list[dict[str, Any]] = []
    header_strip_count = 0

    for row in figure_spec["rows"]:
        if row["kind"] == "header_strip":
            layout_rows.append(
                {
                    "kind": "header_strip",
                    "x": OUTER_MARGIN,
                    "y": y_cursor,
                    "width": content_width,
                    "height": HEADER_STRIP_HEIGHT,
                    "lines": list(row["lines"]),
                }
            )
            y_cursor += HEADER_STRIP_HEIGHT + ROW_GAP
            header_strip_count += 1
            continue

        panels = row["panels"]
        aspect_sum = sum(float(panel["aspect_ratio"]) for panel in panels)
        available_width = content_width - COLUMN_GAP * (len(panels) - 1)
        image_height = max(160, int(round(available_width / aspect_sum)))
        row_height = PANEL_LABEL_HEIGHT + PANEL_LABEL_GAP + image_height
        x_cursor = OUTER_MARGIN
        panel_layouts: list[dict[str, Any]] = []
        for index, panel in enumerate(panels):
            if index == len(panels) - 1:
                panel_width = OUTER_MARGIN + content_width - x_cursor
            else:
                panel_width = int(round(image_height * float(panel["aspect_ratio"])))
            panel_layouts.append(
                {
                    "panel_id": panel["panel_id"],
                    "letter": panel["letter"],
                    "title": panel["title"],
                    "x": x_cursor,
                    "y": y_cursor,
                    "width": panel_width,
                    "height": row_height,
                    "image_x": x_cursor,
                    "image_y": y_cursor + PANEL_LABEL_HEIGHT + PANEL_LABEL_GAP,
                    "image_width": panel_width,
                    "image_height": image_height,
                    "svg_path": panel["svg_path"],
                    "png_path": panel["png_path"],
                }
            )
            x_cursor += panel_width + COLUMN_GAP
        layout_rows.append({"kind": "panel_row", "panels": panel_layouts, "height": row_height})
        y_cursor += row_height + ROW_GAP

    canvas_height = y_cursor - ROW_GAP + OUTER_MARGIN
    return {
        "canvas_width": CANVAS_WIDTH,
        "canvas_height": canvas_height,
        "content_width": content_width,
        "title_lines": title_lines,
        "title_block_height": title_block_height,
        "row_count": len(figure_spec["rows"]),
        "header_strip_count": header_strip_count,
        "rows": layout_rows,
    }


def encode_data_uri(path: Path, mime_type: str) -> str:
    return f"data:{mime_type};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def build_svg_document(figure_spec: dict[str, Any], layout: dict[str, Any]) -> str:
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{layout["canvas_width"]}" height="{layout["canvas_height"]}" viewBox="0 0 {layout["canvas_width"]} {layout["canvas_height"]}">',
        f'  <rect width="{layout["canvas_width"]}" height="{layout["canvas_height"]}" fill="{BACKGROUND_COLOR}"/>',
    ]
    for index, title_line in enumerate(layout.get("title_lines", [str(figure_spec["title"])])):
        title_y = OUTER_MARGIN + 42 + index * TITLE_LINE_HEIGHT
        lines.append(
            f'  <text x="{OUTER_MARGIN}" y="{title_y}" font-family="DejaVu Sans, sans-serif" font-size="40" font-weight="700" fill="{TITLE_COLOR}">{escape(str(title_line))}</text>'
        )
    for row in layout["rows"]:
        if row["kind"] == "header_strip":
            x = row["x"]
            y = row["y"]
            width = row["width"]
            height = row["height"]
            lines.append(
                f'  <rect x="{x}" y="{y}" width="{width}" height="{height}" rx="18" fill="{HEADER_STRIP_FILL}" stroke="{HEADER_STRIP_BORDER}" stroke-width="2"/>'
            )
            for offset, text in enumerate(row["lines"]):
                text_y = y + 34 + offset * 28
                lines.append(
                    f'  <text x="{x + 28}" y="{text_y}" font-family="DejaVu Sans, sans-serif" font-size="22" fill="{TITLE_COLOR}">{escape(text)}</text>'
                )
            continue

        for panel in row["panels"]:
            badge_x = panel["x"]
            badge_y = panel["y"] + 4
            title_x = badge_x + 44
            title_y = badge_y + 23
            lines.append(
                f'  <rect x="{badge_x}" y="{badge_y}" width="30" height="30" rx="8" fill="{PANEL_BADGE_FILL}"/>'
            )
            lines.append(
                f'  <text x="{badge_x + 15}" y="{badge_y + 21}" text-anchor="middle" font-family="DejaVu Sans, sans-serif" font-size="18" font-weight="700" fill="{PANEL_BADGE_TEXT}">{escape(str(panel["letter"]))}</text>'
            )
            lines.append(
                f'  <text x="{title_x}" y="{title_y}" font-family="DejaVu Sans, sans-serif" font-size="22" font-weight="600" fill="{PANEL_LABEL_COLOR}">{escape(str(panel["title"]))}</text>'
            )
            lines.append(
                f'  <rect x="{panel["image_x"]}" y="{panel["image_y"]}" width="{panel["image_width"]}" height="{panel["image_height"]}" fill="#ffffff" stroke="{PANEL_BORDER_COLOR}" stroke-width="2"/>'
            )
            href = encode_data_uri(Path(panel["svg_path"]), "image/svg+xml")
            lines.append(
                f'  <image x="{panel["image_x"]}" y="{panel["image_y"]}" width="{panel["image_width"]}" height="{panel["image_height"]}" preserveAspectRatio="xMidYMid meet" href="{href}" xlink:href="{href}"/>'
            )
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def draw_header_strip(draw: ImageDraw.ImageDraw, row: dict[str, Any], body_font: ImageFont.FreeTypeFont) -> None:
    x = row["x"]
    y = row["y"]
    width = row["width"]
    height = row["height"]
    draw.rounded_rectangle(
        (x, y, x + width, y + height),
        radius=18,
        fill=HEADER_STRIP_FILL,
        outline=HEADER_STRIP_BORDER,
        width=2,
    )
    for offset, text in enumerate(row["lines"]):
        draw.text((x + 28, y + 18 + offset * 30), text, fill=TITLE_COLOR, font=body_font)


def render_png_document(figure_spec: dict[str, Any], layout: dict[str, Any], png_path: Path) -> None:
    title_font = load_font(TITLE_FONT, 40)
    panel_font = load_font(TITLE_FONT, 22)
    body_font = load_font(BODY_FONT, 22)
    badge_font = load_font(TITLE_FONT, 18)

    canvas = Image.new("RGB", (layout["canvas_width"], layout["canvas_height"]), color=BACKGROUND_COLOR)
    draw = ImageDraw.Draw(canvas)
    for index, title_line in enumerate(layout.get("title_lines", [str(figure_spec["title"])])):
        draw.text((OUTER_MARGIN, OUTER_MARGIN + 10 + index * TITLE_LINE_HEIGHT), str(title_line), fill=TITLE_COLOR, font=title_font)

    for row in layout["rows"]:
        if row["kind"] == "header_strip":
            draw_header_strip(draw, row, body_font)
            continue
        for panel in row["panels"]:
            badge_bounds = (panel["x"], panel["y"] + 4, panel["x"] + 30, panel["y"] + 34)
            draw.rounded_rectangle(badge_bounds, radius=8, fill=PANEL_BADGE_FILL)
            letter_text = str(panel["letter"])
            letter_box = draw.textbbox((0, 0), letter_text, font=badge_font)
            letter_width = letter_box[2] - letter_box[0]
            letter_height = letter_box[3] - letter_box[1]
            draw.text(
                (panel["x"] + 15 - letter_width / 2, panel["y"] + 19 - letter_height / 2),
                letter_text,
                fill=PANEL_BADGE_TEXT,
                font=badge_font,
            )
            draw.text((panel["x"] + 44, panel["y"] + 7), str(panel["title"]), fill=PANEL_LABEL_COLOR, font=panel_font)
            draw.rectangle(
                (
                    panel["image_x"],
                    panel["image_y"],
                    panel["image_x"] + panel["image_width"],
                    panel["image_y"] + panel["image_height"],
                ),
                outline=PANEL_BORDER_COLOR,
                width=2,
            )
            source_image = Image.open(panel["png_path"]).convert("RGB")
            resized = source_image.resize((panel["image_width"], panel["image_height"]), Image.Resampling.LANCZOS)
            canvas.paste(resized, (panel["image_x"], panel["image_y"]))

    png_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(png_path)


def build_metadata(
    *,
    figure_spec: dict[str, Any],
    layout: dict[str, Any],
    repo_root: Path,
    svg_path: Path,
    png_path: Path,
    metadata_path: Path,
    generated_at: str,
    source_commit: str,
) -> dict[str, Any]:
    panels: list[dict[str, Any]] = []
    inputs: list[str] = []
    for row in figure_spec["rows"]:
        for panel in row.get("panels", []):
            svg_input = display_path(Path(panel["svg_path"]), repo_root)
            png_input = display_path(Path(panel["png_path"]), repo_root)
            panels.append(
                {
                    "panel_id": panel["panel_id"],
                    "letter": panel["letter"],
                    "title": panel["title"],
                    "svg_path": svg_input,
                    "png_path": png_input,
                }
            )
            inputs.extend([svg_input, png_input])
    payload = {
        "figure_id": figure_spec["figure_id"],
        "figure_number": figure_spec["figure_number"],
        "title": figure_spec["title"],
        "script": display_path(SCRIPT_PATH, repo_root),
        "inputs": sorted(dict.fromkeys(inputs)),
        "outputs": {
            "svg": display_path(svg_path, repo_root),
            "png": display_path(png_path, repo_root),
            "metadata": display_path(metadata_path, repo_root),
        },
        "panels": panels,
        "layout": {
            "canvas_width": layout["canvas_width"],
            "canvas_height": layout["canvas_height"],
            "content_width": layout["content_width"],
            "row_count": layout["row_count"],
            "header_strip_count": layout["header_strip_count"],
        },
        "notes": [
            "Composite figure assembled from existing paper-facing panel assets.",
            "Figure 4 keeps the baseline strip unnumbered.",
        ] if figure_spec["figure_id"] == "figure4" else [
            "Composite figure assembled from existing paper-facing panel assets.",
        ],
    }
    return with_generation_provenance(payload, generated_at=generated_at, source_commit=source_commit)


def write_json(path: Path, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def render_composite_figures(
    *,
    repo_root: Path,
    out_dir: Path,
    figure_specs: list[dict[str, Any]],
    generated_at: str,
    source_commit: str,
) -> list[dict[str, Any]]:
    ensure_panel_assets(figure_specs)
    resolve_panel_dimensions(figure_specs)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest: list[dict[str, Any]] = []
    for figure_spec in figure_specs:
        layout = measure_layout(figure_spec)
        svg_path = out_dir / f"{figure_spec['figure_id']}_composite.svg"
        png_path = out_dir / f"{figure_spec['figure_id']}_composite.png"
        metadata_path = out_dir / f"{figure_spec['figure_id']}_composite.metadata.json"

        svg_path.write_text(build_svg_document(figure_spec, layout), encoding="utf-8")
        render_png_document(figure_spec, layout, png_path)
        metadata = build_metadata(
            figure_spec=figure_spec,
            layout=layout,
            repo_root=repo_root,
            svg_path=svg_path,
            png_path=png_path,
            metadata_path=metadata_path,
            generated_at=generated_at,
            source_commit=source_commit,
        )
        write_json(metadata_path, metadata)
        manifest.append(
            {
                "figure_id": figure_spec["figure_id"],
                "figure_number": figure_spec["figure_number"],
                "title": figure_spec["title"],
                "inputs": metadata["inputs"],
                "outputs": metadata["outputs"],
            }
        )

    write_json(out_dir / "composite_manifest.json", with_generation_provenance({"figures": manifest}, generated_at=generated_at, source_commit=source_commit))
    return manifest


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    out_dir = (repo_root / args.out_dir).resolve()
    generated_at = args.generated_at or utc_now_iso()
    source_commit_ref = str(args.source_commit or "HEAD").strip() or "HEAD"
    source_commit = git_commit_sha(repo_root, source_commit_ref)
    if args.source_commit and source_commit == "unknown":
        raise RuntimeError(f"Unable to resolve --source-commit {args.source_commit!r} via git rev-parse")

    figure_specs = build_default_figure_specs(repo_root, panel_root=(repo_root / args.panel_root).resolve())
    render_composite_figures(
        repo_root=repo_root,
        out_dir=out_dir,
        figure_specs=figure_specs,
        generated_at=generated_at,
        source_commit=source_commit,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
