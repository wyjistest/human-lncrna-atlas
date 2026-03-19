#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def render_overview(summary_path: Path) -> str:
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    result = str(data.get("result") or "unknown").strip()
    passed = data.get("passed_stages", 0)
    failed = data.get("failed_stages", 0)
    first_failed = data.get("first_failed_stage")

    lines = [
        "## Self-hosted fast CI overview",
        "",
        f"- Result: **{result}**",
        f"- Passed stages: {passed}",
        f"- Failed stages: {failed}",
    ]
    if first_failed:
        lines.append(f"- First failed stage: `{first_failed}`")
    else:
        lines.append("- First failed stage: `none`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: render_run_tests_summary_overview.py <summary-json-path>", file=sys.stderr)
        return 2

    sys.stdout.write(render_overview(Path(sys.argv[1])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
