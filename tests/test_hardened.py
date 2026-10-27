"""Each hardened grader against all 8 probes: 12 tasks x 8 probes = 96 labeled cases."""

import re
import unicodedata

import pytest

from audit.generate import load_cases
from audit.graders import GradeContext, hardened
from audit.graders.judge import MockJudge

CASES = load_cases()


@pytest.mark.parametrize("case", CASES, ids=[f"{c['task_id']}-{c['probe']}" for c in CASES])
def test_hardened_matches_label(case, tasks):
    task = tasks[case["task_id"]]
    v = hardened.grade(task, case["output"], GradeContext.for_seed(0), judge=MockJudge())
    assert bool(v["score"]) == case["should_pass"], v["reason"]


def test_every_task_has_all_eight_probes(cases):
    per_task = {}
    for c in cases:
        per_task.setdefault(c["task_id"], set()).add(c["probe"])
    assert len(per_task) == 12
    assert all(len(p) == 8 for p in per_task.values())


def test_table_rejects_ambiguous_dates(tasks):
    task = tasks["T3_cast_types"]
    raw = task["inputs"]["orders_raw.csv"]  # MM/DD/YYYY dates must not be silently accepted
    v = hardened.grade(task, raw, GradeContext.for_seed(0))
    assert v["score"] == 0 and "date" in v["reason"]


def test_table_float_tolerance_and_unicode(tasks):
    task = tasks["T2_join_orders_customers"]
    out = unicodedata.normalize("NFD", task["gold"])
    out = re.sub(r"(\.\d)0$", lambda m: m.group(1), out, flags=re.M)  # 12.50 -> 12.5
    assert out != task["gold"]
    assert hardened.grade(task, out, GradeContext.for_seed(0))["score"] == 1


def test_table_diff_reports_changed_row(tasks, cases):
    task = tasks["T4_revenue_by_region"]
    partial = next(c for c in cases if c["task_id"] == task["id"] and c["probe"] == "partial")
    diff = hardened.table_diff(task, partial["output"])
    assert len(diff["only_in_output"]) == 1 and len(diff["only_in_gold"]) == 1


def test_state_rejects_done_flag_without_data(tasks):
    task = tasks["S1_finalize_run"]
    out = task["inputs"]["run.json"].replace('"running"', '"succeeded"')
    v = hardened.grade(task, out, GradeContext.for_seed(0))
    assert v["score"] == 0 and ("finished_at" in v["reason"] or "rows_written" in v["reason"])
