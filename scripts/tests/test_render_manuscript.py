#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts/paper/render_manuscript.py"
FILTER_PATH = REPO_ROOT / "scripts/paper/pandoc_citation_filter.py"
SOURCE_PATH = REPO_ROOT / "docs/paper/manuscript.md"
OUTPUT_PATH = REPO_ROOT / "docs/paper/build/manuscript_rendered.md"
CSL_PATH = REPO_ROOT / "docs/paper/cell.csl"
RESOURCE_SAFE_TITLE = (
    "Triplex-informed lncRNA–gene candidate networks reveal edge-level "
    "conservation and rewiring across primates"
)


class RenderManuscriptTests(unittest.TestCase):
    def test_render_script_is_pandoc_wrapper(self):
        self.assertTrue(SCRIPT_PATH.exists(), "render script missing")
        script = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("pandoc", script)
        self.assertIn("pandoc_citation_filter.py", script)
        self.assertTrue(FILTER_PATH.exists(), "pandoc citation filter missing")
        self.assertTrue(CSL_PATH.exists(), "Cell CSL missing")

    def test_render_script_generates_rendered_markdown_with_real_references(self):
        self.assertTrue(SOURCE_PATH.exists(), "source manuscript missing")
        self.assertTrue(SCRIPT_PATH.exists(), "render script missing")

        result = subprocess.run(
            ["python3", str(SCRIPT_PATH)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)

        self.assertTrue(OUTPUT_PATH.exists(), "rendered manuscript missing")
        rendered = OUTPUT_PATH.read_text(encoding="utf-8")

        self.assertFalse(rendered.startswith("---\n"))
        self.assertNotIn("bibliography: docs/paper/references.bib", rendered)
        self.assertNotIn("[@statello2021]", rendered)
        self.assertNotIn("::: {#refs}", rendered)
        self.assertIn("## References", rendered)
        self.assertIn("Statello", rendered)
        self.assertIn("Nature Reviews Molecular Cell Biology", rendered)
        references = rendered.split("## References", 1)[1]
        reference_lines = [line for line in references.splitlines() if line.strip()]
        self.assertFalse(any(line.startswith("- ") for line in reference_lines[:5]))
        self.assertIn("RNA-DNA triplexes: molecular mechanisms and functional relevance", rendered)
        self.assertIn("Trends in Biochemical Sciences 49(6).", rendered)
        self.assertIn("pp. 532-544.", rendered)
        self.assertIn("https://doi.org/10.1016/j.tibs.2024.03.009", rendered)
        self.assertIn("Harrison, Peter W.", rendered)
        self.assertIn("Amode, M Ridwan", rendered)
        self.assertNotIn("Harrison, Paul W., et al. (2024). Ensembl 2024", rendered)
        self.assertIn(f"# {RESOURCE_SAFE_TITLE}", rendered)
        self.assertNotIn("reveal conserved and rewired trait-associated gene programs", rendered)
        self.assertIn("## Figure Legends", rendered)
        self.assertNotIn("others", rendered)
        self.assertNotIn('Gr\"utzner', rendered)


if __name__ == "__main__":
    unittest.main()
