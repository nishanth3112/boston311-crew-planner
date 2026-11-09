import json
import runpy

import pytest

from boston311.config import ROOT

check = runpy.run_path(str(ROOT / "scripts" / "check_notebook_outputs.py"))


def problems(*cells, draft=False):
    return check["problems"](json.dumps({"cells": list(cells)}), draft)


def markdown(text):
    return {"cell_type": "markdown", "source": text}


def ran(source, count, *outputs):
    return {
        "cell_type": "code",
        "source": source,
        "execution_count": count,
        "outputs": list(outputs),
    }


def stream(text):
    return {"output_type": "stream", "name": "stdout", "text": text}


def test_a_clean_run_passes():
    assert problems(markdown("# Title"), ran("x = 1", 1), ran("x", 2, stream("1"))) == []


def test_unrun_out_of_order_and_error_cells_fail():
    assert problems(ran("x", None)) == ["1 code cell(s) not run"]
    assert problems(ran("x", 2), ran("y", 1)) == [
        "code cells weren't run once, top to bottom, on a clean kernel"
    ]
    error = {"output_type": "error", "ename": "KeyError", "evalue": "'x'", "traceback": []}
    assert problems(ran("d['x']", 1, error)) == ["code cell 1 raised KeyError"]


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("gsk_" + "a" * 40, "the notebook contains a Groq API key"),
        ("GROQ_API_KEY=abc", "the notebook contains an API key setting"),
        ("/Users/ram/Desktop/x.csv", "the notebook contains a local home path"),
    ],
)
def test_secrets_and_local_paths_fail(text, problem):
    assert problems(ran("print(x)", 1, stream(text))) == [problem]


def test_placeholders_fail_unless_draft():
    note = markdown("> AI use: to be confirmed with the team.")
    assert problems(note) == ["the notebook still has the AI-use note to be confirmed"]
    assert problems(note, draft=True) == []


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("TODO: write this", "a TODO"),
        (
            "_The held-out result is added here once the set is ready._",
            "the held-out analyst eval slot",
        ),
        ("_Added in BOS-11: the staffing plan._", "an unfilled section"),
    ],
)
def test_each_placeholder_is_caught(text, name):
    assert problems(markdown(text)) == [f"the notebook still has {name}"]


def test_a_blank_code_cell_that_ran_keeps_the_order():
    assert problems(ran("x = 1", 1), ran("", 2), ran("x", 3, stream("1"))) == []


def test_placeholders_in_the_report_are_caught():
    assert check["placeholders"](
        "Wording: to be confirmed with the team.", "the analysis report"
    ) == ["the analysis report still has the AI-use note to be confirmed"]


def test_placeholder_text_inside_a_chart_image_is_ignored():
    image = {"output_type": "display_data", "data": {"image/png": "iVBORw0KGgoTODOAAAA"}}
    assert problems(ran("plot()", 1, image)) == []
