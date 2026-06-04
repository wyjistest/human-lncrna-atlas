#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
STYLE_IDS_TO_JUSTIFY = {"Normal", "BodyText", "FirstParagraph"}
MAIN_FIGURE_ASSETS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Figure 1", ("paper_figures/composites/figure1_composite.png",)),
    ("Figure 2", ("paper_figures/native/figure2_native.png",)),
    ("Figure 3", ("paper_figures/native/figure3_native.png",)),
    ("Figure 4", ("paper_figures/native/figure4_native.png",)),
    ("Figure 5", ("paper_figures/native/figure5_native.png",)),
    ("Figure 6", ("paper_figures/composites/figure6_composite.png",)),
)
FIGURE6_PANEL_ASSETS: tuple[tuple[str, str], ...] = (
    ("A", "paper_figures/fig6/fig6A_atlas_wide_evidence.png"),
    ("B", "paper_figures/fig6/fig6B_expression_support.png"),
    ("C", "paper_figures/fig6/fig6C_functional_coherence.png"),
    ("D", "paper_figures/fig6/fig6D_flagship_evidence_card.png"),
)
FIGURE6_COMPOSITE_PATH = "paper_figures/composites/figure6_composite.png"
FIGURE6_COMPOSITE_TITLE = "Figure 6. External evidence layers benchmark and contextualize prioritized modules"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render the manuscript review Markdown and export a DOCX whose body "
            "paragraph styles default to full justification."
        ),
    )
    parser.add_argument(
        "--source",
        default="docs/paper/manuscript.md",
        help="Source manuscript markdown path",
    )
    parser.add_argument(
        "--rendered-markdown",
        default="docs/paper/build/manuscript_rendered.md",
        help="Rendered markdown output path used as the DOCX source",
    )
    parser.add_argument(
        "--output",
        default="docs/paper/build/manuscript_rendered.docx",
        help="Rendered DOCX output path",
    )
    parser.add_argument(
        "--docx-markdown",
        default="docs/paper/build/manuscript_rendered_with_figures.md",
        help="Intermediate markdown used for DOCX export with embedded figure images",
    )
    parser.add_argument(
        "--reference-doc",
        default="docs/paper/build/reference_justified.docx",
        help="Generated Pandoc reference DOCX with justified body styles",
    )
    parser.add_argument(
        "--pandoc",
        default="pandoc",
        help="Pandoc executable to invoke",
    )
    return parser.parse_args()


def resolve_path(repo_root: Path, path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return repo_root / path


def run_step(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def ensure_success(result: subprocess.CompletedProcess[str]) -> int:
    if result.returncode == 0:
        return 0
    sys.stderr.write(result.stderr or result.stdout)
    return result.returncode


def patch_styles_xml(styles_xml: bytes) -> bytes:
    ET.register_namespace("w", WORD_NS)
    root = ET.fromstring(styles_xml)

    for style in root.findall(f"{{{WORD_NS}}}style"):
        style_id = style.get(f"{{{WORD_NS}}}styleId")
        if style_id not in STYLE_IDS_TO_JUSTIFY:
            continue

        ppr = style.find(f"{{{WORD_NS}}}pPr")
        if ppr is None:
            ppr = ET.SubElement(style, f"{{{WORD_NS}}}pPr")

        jc = ppr.find(f"{{{WORD_NS}}}jc")
        if jc is None:
            jc = ET.SubElement(ppr, f"{{{WORD_NS}}}jc")

        jc.set(f"{{{WORD_NS}}}val", "both")

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def write_reference_doc(pandoc: str, destination: Path, repo_root: Path) -> int:
    result = subprocess.run(
        [pandoc, "--print-default-data-file=reference.docx"],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        sys.stderr.write((result.stderr or result.stdout).decode("utf-8", errors="replace"))
        return result.returncode

    source_buffer = io.BytesIO(result.stdout)
    output_buffer = io.BytesIO()

    with zipfile.ZipFile(source_buffer) as source_zip, zipfile.ZipFile(output_buffer, "w") as output_zip:
        for zip_info in source_zip.infolist():
            data = source_zip.read(zip_info.filename)
            if zip_info.filename == "word/styles.xml":
                data = patch_styles_xml(data)
            output_zip.writestr(zip_info, data)

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(output_buffer.getvalue())
    return 0


def split_figure_legends(markdown_text: str) -> tuple[str, str]:
    marker = "\n## Figure Legends\n"
    if marker not in markdown_text:
        return markdown_text, ""
    before, after = markdown_text.split(marker, 1)
    return before.rstrip(), f"## Figure Legends\n{after.lstrip()}"


def figure_legend_map(legends_text: str) -> dict[str, str]:
    if not legends_text:
        return {}

    lines = legends_text.splitlines()
    legends: dict[str, list[str]] = {}
    current_label = ""
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("### Figure "):
            if current_label:
                legends[current_label] = current_lines
            heading_text = line[4:].strip()
            current_label = heading_text.split(".", 1)[0]
            current_lines = [line]
            continue
        if current_label:
            current_lines.append(line)

    if current_label:
        legends[current_label] = current_lines

    return {figure_label: "\n".join(lines).rstrip() for figure_label, lines in legends.items()}


def load_label_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_candidates = (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
    )
    for font_path in font_candidates:
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size=size)
    return ImageFont.load_default()


def render_figure6_composite(repo_root: Path) -> Path:
    output_path = repo_root / FIGURE6_COMPOSITE_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)

    panel_records: list[tuple[str, Image.Image]] = []
    missing_assets: list[str] = []
    for panel_label, panel_text in FIGURE6_PANEL_ASSETS:
        panel_path = repo_root / panel_text
        if not panel_path.exists():
            missing_assets.append(panel_text)
            continue
        panel_records.append((panel_label, Image.open(panel_path).convert("RGB")))

    if missing_assets:
        missing_preview = "\n".join(f"- {path}" for path in missing_assets)
        raise FileNotFoundError(f"Missing Figure 6 panel assets for DOCX export:\n{missing_preview}")

    canvas_width = 2200
    margin = 64
    gap = 42
    title_height = 108
    label_height = 46
    column_width = (canvas_width - (2 * margin) - gap) // 2
    title_font = load_label_font(40)
    label_font = load_label_font(36)

    resized_panels: list[tuple[str, Image.Image]] = []
    for panel_label, panel_image in panel_records:
        scale = column_width / panel_image.width
        resized_height = max(1, round(panel_image.height * scale))
        resized_panels.append((panel_label, panel_image.resize((column_width, resized_height), Image.Resampling.LANCZOS)))

    row_heights = [
        max(resized_panels[0][1].height, resized_panels[1][1].height),
        max(resized_panels[2][1].height, resized_panels[3][1].height),
    ]
    canvas_height = (2 * margin) + title_height + (2 * label_height) + sum(row_heights) + gap
    canvas = Image.new("RGB", (canvas_width, canvas_height), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((margin, margin + 10), FIGURE6_COMPOSITE_TITLE, fill="#102a43", font=title_font)

    positions = [
        (margin, margin + title_height + label_height),
        (margin + column_width + gap, margin + title_height + label_height),
        (margin, margin + title_height + label_height + row_heights[0] + gap + label_height),
        (margin + column_width + gap, margin + title_height + label_height + row_heights[0] + gap + label_height),
    ]
    label_positions = [
        (margin, margin + title_height),
        (margin + column_width + gap, margin + title_height),
        (margin, margin + title_height + label_height + row_heights[0] + gap),
        (margin + column_width + gap, margin + title_height + label_height + row_heights[0] + gap),
    ]

    for (panel_label, panel_image), image_position, label_position in zip(resized_panels, positions, label_positions):
        draw.text(label_position, panel_label, fill="#102a43", font=label_font)
        canvas.paste(panel_image, image_position)

    canvas.save(output_path, dpi=(300, 300))
    return output_path


def render_native_main_figures(repo_root: Path) -> None:
    script_path = repo_root / "scripts/paper/generate_native_main_figures.py"
    result = run_step(["python3", str(script_path)], cwd=repo_root)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "native main figure generation failed")


def figure_markdown(figure_label: str, asset_text: str) -> str:
    return f"![{figure_label}]({asset_text}){{width=6.5in}}"


def figure_asset_map(repo_root: Path) -> dict[str, str]:
    render_native_main_figures(repo_root)
    render_figure6_composite(repo_root)
    assets: dict[str, str] = {}
    missing_assets: list[str] = []

    for figure_label, asset_paths in MAIN_FIGURE_ASSETS:
        for asset_text in asset_paths:
            asset_path = repo_root / asset_text
            if not asset_path.exists():
                missing_assets.append(asset_text)
                continue
            assets[figure_label] = asset_text

    if missing_assets:
        missing_preview = "\n".join(f"- {path}" for path in missing_assets)
        raise FileNotFoundError(f"Missing figure assets for DOCX export:\n{missing_preview}")

    return assets


def insert_figures_after_context(markdown_text: str, legends_text: str, repo_root: Path) -> str:
    assets = figure_asset_map(repo_root)
    legends = figure_legend_map(legends_text)
    paragraphs = markdown_text.split("\n\n")
    inserted: set[str] = set()
    output_paragraphs: list[str] = []

    for paragraph in paragraphs:
        output_paragraphs.append(paragraph)
        for figure_label, asset_text in assets.items():
            if figure_label in inserted:
                continue
            if figure_label in paragraph:
                output_paragraphs.append(figure_markdown(figure_label, asset_text))
                if figure_label in legends:
                    output_paragraphs.append(legends[figure_label])
                inserted.add(figure_label)

    missing_labels = [figure_label for figure_label in assets if figure_label not in inserted]
    if missing_labels:
        missing_preview = "\n".join(f"- {figure_label}" for figure_label in missing_labels)
        raise ValueError(f"Could not place figure images in manuscript context:\n{missing_preview}")

    return "\n\n".join(output_paragraphs).rstrip()


def write_docx_markdown_with_figures(rendered_markdown_path: Path, docx_markdown_path: Path, repo_root: Path) -> None:
    rendered_text = rendered_markdown_path.read_text(encoding="utf-8")
    before_legends, legends = split_figure_legends(rendered_text)
    before_legends = insert_figures_after_context(before_legends, legends, repo_root)
    sections = [before_legends]

    docx_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    docx_markdown_path.write_text("\n\n".join(section for section in sections if section).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    render_script = repo_root / "scripts/paper/render_manuscript.py"
    source_path = resolve_path(repo_root, args.source)
    rendered_markdown_path = resolve_path(repo_root, args.rendered_markdown)
    docx_markdown_path = resolve_path(repo_root, args.docx_markdown)
    output_path = resolve_path(repo_root, args.output)
    reference_doc_path = resolve_path(repo_root, args.reference_doc)

    if not render_script.exists():
        sys.stderr.write(f"Render script missing: {render_script}\n")
        return 1
    if not source_path.exists():
        sys.stderr.write(f"Source manuscript missing: {source_path}\n")
        return 1

    rendered_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    render_result = run_step(
        [
            sys.executable,
            str(render_script),
            "--source",
            str(source_path),
            "--output",
            str(rendered_markdown_path),
            "--pandoc",
            args.pandoc,
        ],
        cwd=repo_root,
    )
    render_status = ensure_success(render_result)
    if render_status != 0:
        return render_status

    reference_status = write_reference_doc(args.pandoc, reference_doc_path, repo_root)
    if reference_status != 0:
        return reference_status

    try:
        write_docx_markdown_with_figures(rendered_markdown_path, docx_markdown_path, repo_root)
    except FileNotFoundError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1

    export_result = run_step(
        [
            args.pandoc,
            str(docx_markdown_path),
            "--from=markdown+tex_math_dollars+pipe_tables+raw_attribute",
            "--to=docx",
            f"--reference-doc={reference_doc_path}",
            "-o",
            str(output_path),
        ],
        cwd=repo_root,
    )
    export_status = ensure_success(export_result)
    if export_status != 0:
        return export_status

    sys.stdout.write(f"Rendered DOCX written to {output_path}\n")
    sys.stdout.write(f"Reference DOCX written to {reference_doc_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
