"""Check that the submission notebook was run top to bottom on a clean kernel and keeps its outputs.

    python scripts/check_notebook_outputs.py notebooks/311_staffing_submission.ipynb

Exits 1 and lists every problem. Standard library only, so CI needs no install.
"""

import json
import sys

KEY_PREFIX = "gsk_"  # Groq API keys; the notebook is committed, so no cell may show one


def problems(notebook: dict) -> list[str]:
    found = []
    code = [
        c for c in notebook["cells"] if c["cell_type"] == "code" and "".join(c["source"]).strip()
    ]
    counts = [c.get("execution_count") for c in code]
    for i, (cell, count) in enumerate(zip(code, counts, strict=True), start=1):
        if count is None:
            found.append(f"code cell {i} was never run")
        if KEY_PREFIX in json.dumps([cell["source"], cell.get("outputs", [])]):
            found.append(f"code cell {i} shows something that looks like an API key")
        for output in cell.get("outputs", []):
            if output.get("output_type") == "error":
                found.append(f"code cell {i} has an error: {output.get('ename')}")
    if None not in counts and counts != list(range(1, len(counts) + 1)):
        found.append(
            "execution counts aren't 1..n in order: run it top to bottom on a fresh kernel"
        )
    return found


def main(path: str) -> int:
    with open(path, encoding="utf-8") as f:
        found = problems(json.load(f))
    for problem in found:
        print(f"{path}: {problem}")
    if not found:
        print(f"{path}: ok")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
