"""Audit-level behaviour: naive failure modes, flakiness detection, judge, mutation test, determinism."""

import filecmp
from pathlib import Path

from audit import DATA_DIR
from audit.generate import generate
from audit.graders import hardened
from audit.graders.judge import MockJudge
from audit.runner import render_report, run_audit


def _case(results, task_id, probe):
    return next(c for c in results["cases"] if c["task_id"] == task_id and c["probe"] == probe)


def test_hardened_has_zero_errors(audit_results):
    h = audit_results["summary"]["hardened"]
    assert (h["fp"], h["fn"], h["flaky"]) == (0, 0, 0)


def test_naive_shows_expected_failure_modes(audit_results):
    r = audit_results
    assert _case(r, "A1_null_customer_ids", "substring_trap")["verdicts"]["naive"]["error"] == "FP"  # "17" ⊃ "7"
    assert _case(r, "S2_requeue_failed_run", "look_done")["verdicts"]["naive"]["error"] == "FP"  # status: done
    assert _case(r, "T3_cast_types", "noop")["verdicts"]["naive"]["error"] == "FP"  # untouched input passes
    assert _case(r, "A2_completed_revenue", "format_variant")["verdicts"]["naive"]["error"] == "FN"  # 9469.3
    assert _case(r, "T5_top_customers", "shuffled")["verdicts"]["naive"]["error"] == "FP"  # order matters
    assert r["summary"]["naive"]["fp"] > 0 and r["summary"]["naive"]["fn"] > 0


def test_flakiness_flags_only_the_planted_grader(audit_results):
    flaky = {(c["task_id"], name) for c in audit_results["cases"]
             for name, v in c["verdicts"].items() if v["flaky"]}
    assert flaky == {("S1_finalize_run", "naive")}


def test_judge_only_called_when_exact_check_fails(audit_results):
    for c in audit_results["cases"]:
        v = c["verdicts"]["hardened"]
        if c["task_type"] != "answer":
            assert v["judge"] is None
        elif v["graded_by"] == "exact":
            assert v["judge"] is None
        else:
            assert v["judge"]["backend"] == "mock"
    assert audit_results["judge"]["evaluation"]["mock"]["disagreements"] == []


def test_mock_judge_rules(tasks):
    j = MockJudge()
    a2 = tasks["A2_completed_revenue"]
    assert j.judge(a2, f"Total is ${float(a2['gold']):,.2f}")["score"] == 1
    assert j.judge(a2, f"{a2['gold']} or maybe {float(a2['gold']) + 1}")["score"] == 0
    assert j.judge(a2, f"not {a2['gold']}")["score"] == 0
    a3 = tasks["A3_top_region"]
    assert j.judge(a3, f"It's {a3['gold'].lower()}!")["score"] == 1


def test_mutation_swap_equality_for_in_is_caught(monkeypatch):
    # Inject a known bug into the hardened answer grader: equality becomes substring containment.
    monkeypatch.setattr(hardened, "_exact", lambda gold, out: gold in out)
    results = run_audit(k=1, judge=MockJudge())
    assert results["summary"]["hardened"]["fp"] > 0
    caught = {(c["task_id"], c["probe"]) for c in results["cases"] if c["verdicts"]["hardened"]["error"]}
    assert ("A1_null_customer_ids", "substring_trap") in caught


def test_report_lists_every_wrong_verdict(audit_results):
    report = render_report(audit_results)
    n_wrong = sum(1 for c in audit_results["cases"] if c["verdicts"]["naive"]["error"])
    assert report.count("- **FP**") + report.count("- **FN**") == n_wrong
    assert "Not affiliated with HUD" in report


def test_generator_is_deterministic_and_matches_committed_data(tmp_path: Path):
    out = generate(tmp_path / "data")
    cmp = filecmp.dircmp(out, DATA_DIR)
    stack, mismatches = [cmp], []
    while stack:
        d = stack.pop()
        mismatches += d.left_only + d.right_only + d.diff_files
        stack += d.subdirs.values()
    assert mismatches == []
    # dircmp compares shallowly by size/mtime; confirm bytes for every file too.
    for f in out.rglob("*"):
        if f.is_file():
            assert f.read_bytes() == (DATA_DIR / f.relative_to(out)).read_bytes(), f
