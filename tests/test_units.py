"""Unit tests for the small building blocks: normalizers, naive graders, the seeded clock, the judges."""

import json
import sys
import types

import pytest

from audit.graders import BASE_NOW, GradeContext, hardened, judge, naive
from audit.graders.hardened import GradeError, normalize_cell, normalize_field, normalize_text, parse_datetime

pytestmark = pytest.mark.unit

ANSWER = {"id": "x", "type": "answer", "answer_kind": "numeric", "gold": "7", "instruction": "How many?"}
TEXT_ANSWER = {**ANSWER, "answer_kind": "text", "gold": "North-East"}
TABLE = {"id": "t", "type": "table", "schema": {"id": "str", "amount": "float"}, "key": ["id"],
         "order_matters": False, "gold": "id,amount\na,1.50\nb,2.00\n"}
STATE = {"id": "s", "type": "state", "target_status": "succeeded",
         "fields": {"status": "enum", "rows_written": "int", "finished_at": "datetime", "outputs": "unordered_list"},
         "gold": json.dumps({"status": "succeeded", "rows_written": 3, "finished_at": "2025-06-01T10:15:00Z",
                             "outputs": ["a", "b"]})}
CTX = GradeContext.for_seed(0)


# ---- normalizers ------------------------------------------------------------------------

@pytest.mark.parametrize("raw,kind,expected", [
    (" 1.50 ", "float", "1.5"), ("1,200.00", "float", "1200.0"), ("1.5000001", "float", "1.5"),
    ("3.0", "int", "3"), ("NULL", "str", None), ("", "float", None), ("n/a", "date", None),
    ("2025/03/04", "date", "2025-03-04"), ("2025-03-04 10:00:00", "datetime", "2025-03-04T10:00:00"),
    ("José", "str", "José"),  # NFD -> NFC
])
def test_normalize_cell(raw, kind, expected):
    assert normalize_cell(raw, kind) == expected


@pytest.mark.parametrize("raw,kind", [("03/04/2025", "date"), ("abc", "float"), ("2.5", "int"), ("x", "datetime")])
def test_normalize_cell_rejects(raw, kind):
    with pytest.raises(GradeError):
        normalize_cell(raw, kind)


def test_datetime_timezones_are_normalized_to_utc():
    assert parse_datetime("2025-06-01T10:15:00Z") == parse_datetime("2025-06-01T15:45:00+05:30")


def test_normalize_field_types():
    assert normalize_field(120.0, "int") == 120
    assert normalize_field(["b", "a"], "unordered_list") == ["a", "b"]
    assert normalize_field("  Succeeded ", "enum") == "succeeded"
    with pytest.raises(GradeError):
        normalize_field("120", "int")  # strings are not silently coerced
    with pytest.raises(GradeError):
        normalize_field(True, "int")


def test_normalize_text():
    assert normalize_text("  NORTH-EAST! ") == "north east"


# ---- seeded clock -----------------------------------------------------------------------

def test_grade_context_is_deterministic_and_bounded():
    for seed in range(20):
        assert GradeContext.for_seed(seed) == GradeContext.for_seed(seed)
        assert 0 <= (GradeContext.for_seed(seed).now - BASE_NOW).total_seconds() <= 600
    assert len({GradeContext.for_seed(s).now for s in range(5)}) == 5  # different seeds, different clocks


# ---- naive graders ----------------------------------------------------------------------

def test_naive_answer_is_a_substring_check():
    assert naive.grade(ANSWER, "17", CTX)["score"] == 1  # the known false positive
    assert naive.grade(ANSWER, "7.0", CTX)["score"] == 1
    assert naive.grade(ANSWER, "seven", CTX)["score"] == 0


def test_naive_table_checks_header_and_row_count_only():
    assert naive.grade(TABLE, "id,amount\na,9.99\nb,9.99\n", CTX)["score"] == 1  # wrong data passes
    assert naive.grade(TABLE, "amount,id\n1.50,a\n2.00,b\n", CTX)["score"] == 0  # right data fails
    assert naive.grade(TABLE, "id,amount\n", CTX)["score"] == 0


def test_naive_state_trusts_status_and_freshness_depends_on_clock():
    task = {**STATE, "naive_freshness_seconds": 300}
    out = STATE["gold"]
    fresh = GradeContext(seed=0, now=parse_dt("2025-06-01T10:16:00+00:00"))
    stale = GradeContext(seed=0, now=parse_dt("2025-06-01T10:30:00+00:00"))
    assert naive.grade(task, out, fresh)["score"] == 1
    assert naive.grade(task, out, stale)["score"] == 0
    assert naive.grade(STATE, json.dumps({"status": "done"}), CTX)["score"] == 1
    assert naive.grade(STATE, "not json", CTX)["score"] == 0


def parse_dt(s):
    from datetime import datetime
    return datetime.fromisoformat(s)


# ---- hardened graders on hand-made inputs -----------------------------------------------

def test_hardened_table():
    assert hardened.grade(TABLE, "AMOUNT , ID\n2,b\n1.5,a\n", CTX)["score"] == 1
    for bad, reason in [("", "empty"), ("id,amount\n", "no data"), ("id,amount\na,1.5\na,1.5\n", "duplicate"),
                        ("id,amount,x\na,1.5,1\nb,2,1\n", "columns"), ("id,amount\na,1.5\nb,2.01\n", "differs")]:
        v = hardened.grade(TABLE, bad, CTX)
        assert v["score"] == 0 and reason in v["reason"], (bad, v)


def test_hardened_table_order_matters():
    ordered = {**TABLE, "order_matters": True}
    assert hardened.grade(ordered, "id,amount\nb,2\na,1.5\n", CTX)["score"] == 0
    assert hardened.grade(ordered, "id,amount\na,1.5\nb,2\n", CTX)["score"] == 1


def test_hardened_state():
    ok = {"outputs": ["b", "a"], "finished_at": "2025-06-01T10:15:00+00:00", "rows_written": 3.0, "status": "SUCCEEDED"}
    assert hardened.grade(STATE, json.dumps(ok), CTX)["score"] == 1
    for bad in [{**ok, "rows_written": 4}, {**ok, "status": "not_succeeded"}, {**ok, "extra": 1},
                {k: v for k, v in ok.items() if k != "finished_at"}]:
        assert hardened.grade(STATE, json.dumps(bad), CTX)["score"] == 0, bad
    assert hardened.grade(STATE, "[1, 2]", CTX)["score"] == 0
    assert hardened.grade(STATE, "{oops", CTX)["score"] == 0


def test_hardened_answer_uses_exact_before_judge():
    calls = []

    class SpyJudge:
        name = "spy"

        def judge(self, task, output):
            calls.append(output)
            return {"score": 0, "reason": "spy"}

    assert hardened.grade(ANSWER, " 7 ", CTX, judge=SpyJudge())["graded_by"] == "exact"
    assert calls == []
    v = hardened.grade(ANSWER, "seven", CTX, judge=SpyJudge())
    assert v["graded_by"] == "judge" and calls == ["seven"]


# ---- judges -----------------------------------------------------------------------------

@pytest.mark.parametrize("task,output,score", [
    (ANSWER, "There are 7 rows.", 1), (ANSWER, "7.001", 1), (ANSWER, "7.01", 0), (ANSWER, "7 or 8", 0),
    (ANSWER, "It isn't 7", 0), (ANSWER, "", 0), (ANSWER, "none", 0),
    (TEXT_ANSWER, "north east it is", 1), (TEXT_ANSWER, "North", 0), (TEXT_ANSWER, "not North-East", 0),
])
def test_mock_judge(task, output, score):
    assert judge.MockJudge().judge(task, output)["score"] == score


def _fake_litellm(monkeypatch, completion):
    mod = types.ModuleType("litellm")
    mod.completion = completion
    monkeypatch.setitem(sys.modules, "litellm", mod)


def test_get_judge_defaults_to_mock(monkeypatch):
    monkeypatch.delenv("JUDGE_MODEL", raising=False)
    assert judge.get_judge().name == "mock"


def test_llm_judge_parses_model_reply(monkeypatch):
    reply = types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(
        content='Sure: {"verdict": "pass", "reason": "same number"}'))])
    _fake_litellm(monkeypatch, lambda **kw: reply)
    monkeypatch.setenv("JUDGE_MODEL", "fake/model")
    j = judge.get_judge()
    assert j.name == "llm:fake/model"
    assert j.judge(ANSWER, "seven") == {"score": 1, "reason": "same number"}


def test_llm_judge_falls_back_to_mock_on_error(monkeypatch):
    def boom(**kw):
        raise ConnectionError("no network")

    _fake_litellm(monkeypatch, boom)
    r = judge.LLMJudge("fake/model").judge(ANSWER, "17")
    assert r["score"] == 0 and r["reason"].startswith("[LLM error: ConnectionError; mock used]")
