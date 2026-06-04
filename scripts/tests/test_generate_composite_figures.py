#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts/paper/generate_composite_figures.py"


def load_module():
    if not MODULE_PATH.exists():
        raise AssertionError(f"missing module under test: {MODULE_PATH}")
    spec = importlib.util.spec_from_file_location("generate_composite_figures", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_dummy_panel_assets(base_dir: Path, panel_rel_path: str, *, width: int, height: int) -> tuple[Path, Path]:
    svg_path = base_dir / panel_rel_path
    png_path = svg_path.with_suffix(".png")
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_text(
        "\n".join(
            [
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}pt" height="{height}pt" viewBox="0 0 {width} {height}">',
                f'  <rect width="{width}" height="{height}" fill="#eef3f8" stroke="#284b63" stroke-width="4"/>',
                f'  <text x="{width / 2:.1f}" y="{height / 2:.1f}" text-anchor="middle" font-size="24" fill="#102a43">{svg_path.stem}</text>',
                "</svg>",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    Image.new("RGB", (width, height), color=(238, 243, 248)).save(png_path)
    return svg_path, png_path


class GenerateCompositeFiguresTests(unittest.TestCase):
    def test_parse_args_uses_composite_output_dir_and_source_commit(self):
        module = load_module()
        original_argv = sys.argv[:]
        try:
            sys.argv = ["generate_composite_figures.py"]
            args = module.parse_args()
        finally:
            sys.argv = original_argv

        self.assertEqual(args.out_dir, "paper_figures/composites")
        self.assertTrue(hasattr(args, "source_commit"))
        self.assertIsNone(args.source_commit)

    def test_build_default_figure_specs_matches_locked_panel_structure(self):
        module = load_module()

        specs = module.build_default_figure_specs(REPO_ROOT)
        self.assertEqual([spec["figure_number"] for spec in specs], [1, 2, 3, 4, 5])

        spec1 = specs[0]
        self.assertEqual(
            [panel["panel_id"] for row in spec1["rows"] for panel in row.get("panels", [])],
            ["fig1A", "fig1B", "fig1C", "fig1D"],
        )
        self.assertEqual([len(row.get("panels", [])) for row in spec1["rows"]], [2, 1, 1])
        self.assertEqual(spec1["rows"][1]["panels"][0]["title"], "Orthology-aware triplex workflow")
        self.assertEqual(spec1["rows"][2]["panels"][0]["title"], "Frozen submission snapshot")

        spec2 = specs[1]
        self.assertEqual(
            spec2["title"],
            "Figure 2. Global architecture of primate candidate lncRNA–gene networks",
        )
        self.assertNotIn("regulatory networks", spec2["title"])

        spec3 = specs[2]
        self.assertEqual(
            spec3["title"],
            "Figure 3. Cross-species conservation and lineage-specific rewiring of candidate lncRNA–PCG edges",
        )
        self.assertEqual([len(row.get("panels", [])) for row in spec3["rows"]], [2, 2, 1])
        self.assertEqual(
            [panel["panel_id"] for row in spec3["rows"] for panel in row.get("panels", [])],
            ["fig3A", "fig3B", "fig3C", "fig3D", "fig3E"],
        )
        spec3c = next(panel for row in spec3["rows"] for panel in row.get("panels", []) if panel["panel_id"] == "fig3C")
        spec3d = next(panel for row in spec3["rows"] for panel in row.get("panels", []) if panel["panel_id"] == "fig3D")
        spec3e = next(panel for row in spec3["rows"] for panel in row.get("panels", []) if panel["panel_id"] == "fig3E")
        self.assertEqual(spec3c["title"], "Species-pair node and edge sharing")
        self.assertEqual(spec3d["letter"], "D")
        self.assertEqual(spec3d["title"], "Illustrative conserved and rewired candidate examples")
        self.assertEqual(spec3e["letter"], "E")
        self.assertEqual(spec3e["title"], "Observed-vs-null calibration")
        self.assertEqual(spec3e["svg_path"].name, "fig3E_null_calibration.svg")

        spec4 = specs[3]
        self.assertEqual(spec4["rows"][0]["kind"], "header_strip")
        self.assertEqual(
            spec4["rows"][0]["lines"][1],
            "Cross-mark subset: A549 | GM12878 | H1-hESC | HepG2 | HMEC | K562",
        )
        self.assertEqual(
            [panel["letter"] for row in spec4["rows"][1:] for panel in row.get("panels", [])],
            ["A", "B", "C", "D"],
        )
        spec4d = next(panel for row in spec4["rows"] for panel in row.get("panels", []) if panel["panel_id"] == "fig4D")
        self.assertEqual(spec4d["title"], "Representative local epigenomic tracks")

    def test_render_composite_figures_writes_svg_png_and_metadata(self):
        module = load_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            panel_root = repo_root / "paper_figures"
            out_dir = repo_root / "paper_figures/composites"
            input_paths: list[Path] = []
            for panel_name, size in {
                "fig1/fig1A_catalog_gap.svg": (640, 320),
                "fig1/fig1B_ortholog_mapping.svg": (720, 360),
                "fig1/fig1C_workflow.svg": (760, 300),
                "fig1/fig1D_kpi.svg": (680, 420),
            }.items():
                svg_path, png_path = write_dummy_panel_assets(panel_root, panel_name, width=size[0], height=size[1])
                input_paths.extend([svg_path, png_path])

            figure_spec = {
                "figure_number": 1,
                "figure_id": "figure1",
                "title": "Figure 1. Composite smoke test",
                "rows": [
                    {
                        "kind": "panel_row",
                        "panels": [
                            {
                                "panel_id": "fig1A",
                                "letter": "A",
                                "title": "Catalog gap",
                                "svg_path": panel_root / "fig1/fig1A_catalog_gap.svg",
                                "png_path": panel_root / "fig1/fig1A_catalog_gap.png",
                            },
                            {
                                "panel_id": "fig1B",
                                "letter": "B",
                                "title": "Ortholog mapping",
                                "svg_path": panel_root / "fig1/fig1B_ortholog_mapping.svg",
                                "png_path": panel_root / "fig1/fig1B_ortholog_mapping.png",
                            },
                        ],
                    },
                    {
                        "kind": "panel_row",
                        "panels": [
                            {
                                "panel_id": "fig1C",
                                "letter": "C",
                                "title": "Workflow",
                                "svg_path": panel_root / "fig1/fig1C_workflow.svg",
                                "png_path": panel_root / "fig1/fig1C_workflow.png",
                            },
                            {
                                "panel_id": "fig1D",
                                "letter": "D",
                                "title": "Frozen snapshot",
                                "svg_path": panel_root / "fig1/fig1D_kpi.svg",
                                "png_path": panel_root / "fig1/fig1D_kpi.png",
                            },
                        ],
                    },
                ],
            }

            manifest = module.render_composite_figures(
                repo_root=repo_root,
                out_dir=out_dir,
                figure_specs=[figure_spec],
                generated_at="2026-04-22T08:30:00Z",
                source_commit="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
            )

            self.assertEqual(len(manifest), 1)
            entry = manifest[0]
            svg_path = out_dir / "figure1_composite.svg"
            png_path = out_dir / "figure1_composite.png"
            metadata_path = out_dir / "figure1_composite.metadata.json"

            self.assertTrue(svg_path.exists())
            self.assertTrue(png_path.exists())
            self.assertTrue(metadata_path.exists())
            self.assertEqual(entry["outputs"]["svg"], "paper_figures/composites/figure1_composite.svg")
            self.assertEqual(entry["figure_id"], "figure1")

            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["figure_id"], "figure1")
            self.assertEqual(metadata["generated_at"], "2026-04-22T08:30:00Z")
            self.assertEqual(metadata["source_commit"], "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef")
            self.assertEqual(len(metadata["panels"]), 4)
            self.assertEqual(metadata["layout"]["row_count"], 2)
            self.assertEqual(metadata["layout"]["header_strip_count"], 0)
            self.assertEqual(sorted(metadata["inputs"]), sorted(path.relative_to(repo_root).as_posix() for path in input_paths))

    def test_generated_composite_svgs_keep_contiguous_scientific_abbreviations(self):
        figure2_svg = REPO_ROOT / "paper_figures/composites/figure2_composite.svg"
        figure5_svg = REPO_ROOT / "paper_figures/composites/figure5_composite.svg"
        self.assertTrue(figure2_svg.exists(), f"missing generated svg: {figure2_svg}")
        self.assertTrue(figure5_svg.exists(), f"missing generated svg: {figure5_svg}")

        figure2_text = figure2_svg.read_text(encoding="utf-8")
        figure5_text = figure5_svg.read_text(encoding="utf-8")

        self.assertIn("lncRNA", figure2_text)
        self.assertIn("lncRNA", figure5_text)
        self.assertNotIn("l ncRNA", figure2_text)
        self.assertNotIn("l ncRNA", figure5_text)

    def test_generated_figure3_composite_metadata_includes_observed_null_panel(self):
        metadata_path = REPO_ROOT / "paper_figures/composites/figure3_composite.metadata.json"
        self.assertTrue(metadata_path.exists(), f"missing generated metadata: {metadata_path}")

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        panel_ids = [panel["panel_id"] for panel in metadata.get("panels", [])]
        self.assertEqual(panel_ids, ["fig3A", "fig3B", "fig3C", "fig3D", "fig3E"])
        self.assertEqual(metadata["layout"]["row_count"], 3)
        self.assertIn("paper_figures/fig3/fig3E_null_calibration.svg", metadata["inputs"])
        self.assertNotIn("regulatory networks", metadata["title"])


if __name__ == "__main__":
    unittest.main()
