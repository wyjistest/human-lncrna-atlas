#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
import hashlib
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts/paper/export_manuscript_docx.py"
WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
STYLE_IDS_TO_JUSTIFY = {"Normal", "BodyText", "FirstParagraph"}


def load_module():
    if not SCRIPT_PATH.exists():
        raise AssertionError(f"missing module under test: {SCRIPT_PATH}")
    spec = importlib.util.spec_from_file_location("export_manuscript_docx", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def style_alignment_map(docx_path: Path) -> dict[str, str]:
    with zipfile.ZipFile(docx_path) as archive:
        styles_xml = archive.read("word/styles.xml")

    root = ET.fromstring(styles_xml)
    alignments: dict[str, str] = {}
    for style in root.findall(f"{{{WORD_NS}}}style"):
        style_id = style.get(f"{{{WORD_NS}}}styleId")
        if style_id not in STYLE_IDS_TO_JUSTIFY:
            continue
        ppr = style.find(f"{{{WORD_NS}}}pPr")
        jc = None if ppr is None else ppr.find(f"{{{WORD_NS}}}jc")
        alignments[style_id] = "" if jc is None else jc.get(f"{{{WORD_NS}}}val", "")
    return alignments


def docx_media_files(docx_path: Path) -> list[str]:
    with zipfile.ZipFile(docx_path) as archive:
        return sorted(name for name in archive.namelist() if name.startswith("word/media/"))


def docx_body_text(docx_path: Path) -> str:
    with zipfile.ZipFile(docx_path) as archive:
        document_xml = archive.read("word/document.xml")

    root = ET.fromstring(document_xml)
    return "\n".join(node.text or "" for node in root.findall(f".//{{{WORD_NS}}}t"))


class ExportManuscriptDocxTests(unittest.TestCase):
    def test_native_figure_refresh_uses_current_python_interpreter(self):
        module = load_module()
        captured_commands: list[list[str]] = []

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        def capture_run_step(command: list[str], *, cwd: Path):
            captured_commands.append(command)
            return Result()

        module.run_step = capture_run_step

        with tempfile.TemporaryDirectory() as temp_dir:
            module.render_native_main_figures(Path(temp_dir))

        self.assertEqual(1, len(captured_commands))
        self.assertEqual(sys.executable, captured_commands[0][0])

    def test_figure_asset_map_reuses_existing_assets_without_regenerating_tracked_figures(self):
        module = load_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            asset_paths = (
                "paper_figures/composites/figure1_composite.png",
                "paper_figures/native/figure2_native.png",
                "paper_figures/native/figure3_native.png",
                "paper_figures/native/figure4_native.png",
                "paper_figures/native/figure5_native.png",
                "paper_figures/composites/figure6_composite.png",
            )
            for asset_path_text in asset_paths:
                asset_path = repo_root / asset_path_text
                asset_path.parent.mkdir(parents=True, exist_ok=True)
                Image.new("RGB", (8, 8), color=(255, 255, 255)).save(asset_path)

            def fail_render(*_args, **_kwargs):
                raise AssertionError("figure generators should not run when assets already exist")

            module.render_native_main_figures = fail_render
            module.render_figure6_composite = fail_render

            self.assertEqual(
                {
                    "Figure 1": "paper_figures/composites/figure1_composite.png",
                    "Figure 2": "paper_figures/native/figure2_native.png",
                    "Figure 3": "paper_figures/native/figure3_native.png",
                    "Figure 4": "paper_figures/native/figure4_native.png",
                    "Figure 5": "paper_figures/native/figure5_native.png",
                    "Figure 6": "paper_figures/composites/figure6_composite.png",
                },
                module.figure_asset_map(repo_root),
            )

    def test_export_script_generates_justified_reference_doc_and_docx(self):
        self.assertTrue(SCRIPT_PATH.exists(), "DOCX export script missing")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            rendered_markdown_path = temp_path / "manuscript_rendered.md"
            docx_markdown_path = temp_path / "manuscript_rendered_with_figures.md"
            output_path = temp_path / "manuscript_rendered.docx"
            reference_doc_path = temp_path / "reference_justified.docx"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--rendered-markdown",
                    str(rendered_markdown_path),
                    "--docx-markdown",
                    str(docx_markdown_path),
                    "--output",
                    str(output_path),
                    "--reference-doc",
                    str(reference_doc_path),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)

            self.assertTrue(rendered_markdown_path.exists(), "rendered markdown missing")
            self.assertTrue(docx_markdown_path.exists(), "DOCX markdown missing")
            self.assertTrue(reference_doc_path.exists(), "reference doc missing")
            self.assertTrue(output_path.exists(), "rendered DOCX missing")

            for docx_path in [reference_doc_path, output_path]:
                alignment_map = style_alignment_map(docx_path)
                self.assertEqual(STYLE_IDS_TO_JUSTIFY, set(alignment_map))
                for style_id in STYLE_IDS_TO_JUSTIFY:
                    self.assertEqual(
                        "both",
                        alignment_map[style_id],
                        msg=f"{docx_path} style {style_id} is not justified",
                    )

            media_files = docx_media_files(output_path)
            self.assertEqual(6, len(media_files), msg=f"expected one embedded image per main figure: {media_files}")

            body_text = docx_body_text(output_path)
            self.assertIn(
                "Figure 1. From prior trait-associated gene catalogs to orthology-aware candidate lncRNA–PCG edges",
                body_text,
            )
            self.assertIn(
                "Figure 6. External evidence layers benchmark and contextualize prioritized modules",
                body_text,
            )
            self.assertNotIn("{width=6.5in}", body_text)

            docx_markdown = docx_markdown_path.read_text(encoding="utf-8")
            self.assertNotIn("## Main Figures", docx_markdown)
            self.assertNotIn("## Figure Legends", docx_markdown)
            self.assertIn("paper_figures/composites/figure6_composite.png", docx_markdown)
            for figure_number in range(2, 6):
                self.assertIn(f"paper_figures/native/figure{figure_number}_native.png", docx_markdown)
                self.assertNotIn(f"paper_figures/composites/figure{figure_number}_composite.png", docx_markdown)
            self.assertNotIn("paper_figures/fig6/fig6A_atlas_wide_evidence.png", docx_markdown)

            figure1_context = "The overall workflow and frozen snapshot are summarized in Figure 1."
            figure1_image = "![Figure 1](paper_figures/composites/figure1_composite.png){width=6.5in}"
            figure1_legend = "### Figure 1. From prior trait-associated gene catalogs to orthology-aware candidate lncRNA–PCG edges"
            figure6_context = "Figure 6 summarizes atlas-wide external evidence"
            figure6_next_context = "PCG target-program expression context was summarized as a mappable subset analysis"
            figure6_image = "![Figure 6](paper_figures/composites/figure6_composite.png){width=6.5in}"
            figure6_legend = "### Figure 6. External evidence layers benchmark and contextualize prioritized modules"
            self.assertLess(docx_markdown.index(figure1_context), docx_markdown.index(figure1_image))
            self.assertLess(docx_markdown.index(figure1_image), docx_markdown.index(figure1_legend))
            self.assertLess(docx_markdown.index(figure1_legend), docx_markdown.index("Global network architecture"))
            self.assertLess(docx_markdown.index(figure6_context), docx_markdown.index(figure6_image))
            self.assertLess(docx_markdown.index(figure6_image), docx_markdown.index(figure6_legend))
            self.assertLess(docx_markdown.index(figure6_legend), docx_markdown.index(figure6_next_context))

            figure6_composite_path = REPO_ROOT / "paper_figures/composites/figure6_composite.png"
            with Image.open(figure6_composite_path) as figure6_image_obj:
                self.assertGreaterEqual(figure6_image_obj.height, 1800)
            figure6_digest = hashlib.sha256(figure6_composite_path.read_bytes()).hexdigest()
            with zipfile.ZipFile(output_path) as archive:
                media_digests = {
                    hashlib.sha256(archive.read(name)).hexdigest()
                    for name in archive.namelist()
                    if name.startswith("word/media/")
                }
            self.assertIn(figure6_digest, media_digests)


if __name__ == "__main__":
    unittest.main()
