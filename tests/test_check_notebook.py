import json
import subprocess
import sys

import pytest

from boston311.config import ROOT

SCRIPT = ROOT / "scripts" / "check_notebook_outputs.py"
NOTEBOOK = ROOT / "notebooks" / "311_staffing_submission.ipynb"


def cell(count, outputs=(), source="x = 1"):
    return {
        "cell_type": "code",
        "source": [source],
        "execution_count": count,
        "outputs": list(outputs),
    }


def check(tmp_path, cells) -> subprocess.CompletedProcess:
    path = tmp_path / "nb.ipynb"
    path.write_text(json.dumps({"cells": cells}))
    return subprocess.run([sys.executable, SCRIPT, path], capture_output=True, text=True)


def test_a_clean_run_passes(tmp_path):
    markdown = {"cell_type": "markdown", "source": ["# Title"]}
    blank = cell(None, source="  ")  # empty code cells don't count
    result = check(tmp_path, [markdown, cell(1), blank, cell(2, [{"output_type": "stream"}])])
    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize(
    ("cells", "message"),
    [
        ([cell(1), cell(None)], "never run"),
        ([cell(2), cell(1)], "1..n in order"),
        ([cell(1), cell(3)], "1..n in order"),
        ([cell(1, [{"output_type": "error", "ename": "KeyError"}])], "error: KeyError"),
        ([cell(1, [{"output_type": "stream", "text": ["key gsk_abc123"]}])], "API key"),
        ([cell(1, source='key = "gsk_abc123"')], "API key"),
    ],
)
def test_problems_fail_and_are_named(tmp_path, cells, message):
    result = check(tmp_path, cells)
    assert result.returncode == 1 and message in result.stdout


def test_the_submission_notebook_passes():
    result = subprocess.run([sys.executable, SCRIPT, NOTEBOOK], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
