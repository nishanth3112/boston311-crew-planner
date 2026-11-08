"""Check the submission notebook is ready to hand in.

    uv run python scripts/check_notebook_outputs.py [--draft] [notebook]

Fails (exit 1) when a code cell wasn't run, the cells weren't run once in order on a clean
kernel, any output is an error, the notebook holds something that must not be committed (an
API key, a local path), or a placeholder is still in it or in the analysis report. --draft
skips the placeholder checks. Standard library only: a notebook is JSON.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "311_staffing_submission.ipynb"
REPORT = ROOT / "reports" / "analysis_report.md"
SECRETS = {
    "a Groq API key": re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    "an API key setting": re.compile(r"(GROQ|LANGSMITH|OPENAI)_API_KEY\s*=\s*\S"),
    "a local home path": re.compile(r"/(Users|home)/[A-Za-z0-9._-]+/"),
}
PLACEHOLDERS = {
    "the AI-use note to be confirmed": "to be confirmed with the team",
    "the held-out analyst eval slot": "is added here once",
    "an unfilled section": "_Added in BOS-11",
    "a TODO": "TODO",
}


def _source(cell: dict) -> str:
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else source


def problems(text: str, draft: bool = False) -> list[str]:
    """What stops the notebook (its JSON text) from being handed in; empty when it's ready."""
    cells = json.loads(text)["cells"]
    code = [c for c in cells if c["cell_type"] == "code"]
    found = []
    unrun = [c for c in code if _source(c).strip() and c.get("execution_count") is None]
    if unrun:
        found.append(f"{len(unrun)} code cell(s) not run")
    # every run cell takes a number, blank ones included
    counts = [c["execution_count"] for c in code if c.get("execution_count") is not None]
    if not unrun and counts != list(range(1, len(counts) + 1)):
        found.append("code cells weren't run once, top to bottom, on a clean kernel")
    for i, cell in enumerate(code, 1):
        for output in cell.get("outputs", []):
            if output.get("output_type") == "error":
                found.append(f"code cell {i} raised {output.get('ename')}")
    for name, pattern in SECRETS.items():
        if pattern.search(text):
            found.append(f"the notebook contains {name}")
    if not draft:
        found += placeholders(text, "the notebook")
    return found


def placeholders(text: str, where: str) -> list[str]:
    return [f"{where} still has {name}" for name, marker in PLACEHOLDERS.items() if marker in text]


def main(args: list[str]) -> int:
    draft = "--draft" in args
    paths = [a for a in args if not a.startswith("--")]
    path = Path(paths[0]) if paths else NOTEBOOK
    found = problems(path.read_text(), draft)
    if not draft and REPORT.exists():
        found += placeholders(REPORT.read_text(), "the analysis report")
    for problem in found:
        print(f"FAIL: {problem}")
    if not found:
        print(f"OK: {path.name} is ready" + (" (draft: placeholders not checked)" if draft else ""))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
