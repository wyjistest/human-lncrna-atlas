#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts/paper/generate_native_main_figures.py"


def load_module():
    if not MODULE_PATH.exists():
        raise AssertionError(f"missing module under test: {MODULE_PATH}")
    spec = importlib.util.spec_from_file_location("generate_native_main_figures", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class GenerateNativeMainFiguresTests(unittest.TestCase):
    def test_parse_args_defaults_to_native_output_dir(self):
        module = load_module()
        original_argv = sys.argv[:]
        try:
            sys.argv = ["generate_native_main_figures.py"]
            args = module.parse_args()
        finally:
            sys.argv = original_argv

        self.assertEqual(args.out_dir, "paper_figures/native")
        self.assertEqual(args.panel_root, "paper_figures")

    def test_existing_native_metadata_declares_single_figure_rendering(self):
        for figure_number in range(2, 6):
            metadata_path = REPO_ROOT / f"paper_figures/native/figure{figure_number}_native.metadata.json"
            self.assertTrue(metadata_path.exists(), f"missing native metadata: {metadata_path}")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata.get("figure_id"), f"figure{figure_number}")
            self.assertEqual(metadata.get("rendering_mode"), "native_matplotlib_single_figure")
            self.assertTrue(metadata.get("uses_panel_png_paste") is False)
            self.assertNotIn("Composite figure assembled from existing paper-facing panel assets.", metadata.get("notes", []))
            for input_path in metadata.get("inputs", []):
                self.assertNotRegex(input_path, r"_composite\\.(png|svg)$")
                self.assertNotRegex(input_path, r"fig[2-5][A-E]_.*\\.(png|svg)$")

    def test_existing_native_svgs_do_not_embed_raster_panels(self):
        for figure_number in range(2, 6):
            svg_path = REPO_ROOT / f"paper_figures/native/figure{figure_number}_native.svg"
            self.assertTrue(svg_path.exists(), f"missing native SVG: {svg_path}")
            svg_text = svg_path.read_text(encoding="utf-8")
            self.assertNotIn("<image", svg_text)
            self.assertNotIn("data:image", svg_text)


if __name__ == "__main__":
    unittest.main()
