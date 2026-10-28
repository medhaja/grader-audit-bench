"""Collect every value and code excerpt the video shows, straight from the repo, into facts.json.

Nothing on screen is typed by hand: numbers come from results/results.json and data/, code comes from
the source files (each excerpt is checked against an expected first-line prefix so a moved line fails
the build instead of showing stale code). Standard library only; reads the repo, never reruns the audit.

Usage: python facts.py
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO))

from audit.graders import BASE_NOW, GradeContext  # noqa: E402  (stdlib-only module)

# (id, file, [line numbers or "..."], expected prefix of the first listed line after stripping)
EXCERPTS = [
    ("naive_table", "audit/graders/naive.py", list(range(25, 33)), "def grade_table("),
    ("hardened_table", "audit/graders/hardened.py",
     [126, 127, 128, 129, "...", 134, "...", 139, 140, 141, 142, "...", 144, 145, 146, 147],
     "def grade_table("),
    ("naive_answer_if", "audit/graders/naive.py", [20], 'if task["gold"] in output:'),
    ("hardened_exact", "audit/graders/hardened.py", [87], "if _exact(normalize_text("),
    ("error_rule", "audit/runner.py", [56, 57], 'v["error"] = ("FP"'),
    ("naive_state_if", "audit/graders/naive.py", [42], "if target not in status"),
    ("float_norm", "audit/graders/hardened.py", [69], "return repr(round(float("),
    ("date_formats", "audit/graders/hardened.py", [25], "DATE_FORMATS = "),
]


def read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def excerpt(file: str, lines: list, prefix: str) -> dict:
    src = read(file).splitlines()
    nums = [n for n in lines if n != "..."]
    if not src[nums[0] - 1].strip().startswith(prefix):
        sys.exit(f"{file}:{nums[0]} no longer starts with {prefix!r}; update EXCERPTS and script.md")
    indent = min(len(src[n - 1]) - len(src[n - 1].lstrip()) for n in nums if src[n - 1].strip())
    return {"file": file, "lines": [["...", "…"] if n == "..." else [n, src[n - 1][indent:]] for n in lines]}


def main() -> None:
    results = json.loads(read("results/results.json"))
    case = {(c["task_id"], c["probe"]): c for c in results["cases"]}
    task = lambda tid: json.loads(read(f"data/tasks/{tid}/task.json"))  # noqa: E731

    a1 = case[("A1_null_customer_ids", "substring_trap")]
    t4 = case[("T4_revenue_by_region", "partial")]
    s1 = case[("S1_finalize_run", "gold")]

    # The one changed row in T4 × partial, found by comparing the probe CSV with gold.
    gold_rows = list(csv.DictReader(io.StringIO(read("data/tasks/T4_revenue_by_region/gold.csv"))))
    out_rows = list(csv.DictReader(io.StringIO(read("data/probes/T4_revenue_by_region/partial.csv"))))
    changed = [(g, o) for g, o in zip(gold_rows, out_rows) if g != o]
    assert len(changed) == 1, changed
    t4_gold, t4_out = changed[0]

    s1_task = task("S1_finalize_run")
    window = s1_task["naive_freshness_seconds"]
    delays = [round((GradeContext.for_seed(s).now - BASE_NOW).total_seconds(), 1) for s in range(results["meta"]["k"])]
    assert [int(d <= window) for d in delays] == s1["verdicts"]["naive"]["runs"], "clock model disagrees with results"

    flaky = sorted({(c["task_id"], g) for c in results["cases"] for g, v in c["verdicts"].items() if v["flaky"]})
    serve_lines = [f"  {n:9s} FP {s['fp']}/{s['negatives']}  FN {s['fn']}/{s['positives']}  flaky {s['flaky']}/{s['total']}"
                   for n, s in results["summary"].items()]  # same format as audit/serve.py:106
    tests = int(re.search(r"all (\d+) tests", read("README.md")).group(1))

    facts = {
        "meta": {"k": results["meta"]["k"], "judge_backend": results["meta"]["judge_backend"],
                 "n_cases": results["meta"]["n_cases"], "probes": results["meta"]["probes"]},
        "summary": results["summary"],
        "labels": [[c["task_id"], c["probe"], c["should_pass"]] for c in results["cases"]],
        "a1": {"instruction": task("A1_null_customer_ids")["instruction"],
               "gold": read("data/tasks/A1_null_customer_ids/gold.txt").strip(),
               "output": read("data/probes/A1_null_customer_ids/substring_trap.txt").strip(),
               "naive": a1["verdicts"]["naive"], "hardened": a1["verdicts"]["hardened"]},
        "t4": {"region": t4_out["region"], "got": t4_out["total_amount"], "want": t4_gold["total_amount"],
               "naive": t4["verdicts"]["naive"], "hardened": t4["verdicts"]["hardened"]},
        "s1": {"gold": json.loads(read("data/tasks/S1_finalize_run/gold.json")), "window": window,
               "base_now": BASE_NOW.strftime("%H:%M:%S"), "delays": delays,
               "naive": s1["verdicts"]["naive"]},
        "state_traps": [[tid, case[(tid, "substring_trap")]["verdicts"]["naive"]["error"],
                         case[(tid, "substring_trap")]["verdicts"]["naive"]["reason"]]
                        for tid in ("S1_finalize_run", "S2_requeue_failed_run", "S3_advance_watermark")],
        "flaky": flaky,
        "serve_lines": serve_lines,
        "headline": results["headline"],
        "tests": tests,
        "code": {k: excerpt(f, ln, p) for k, f, ln, p in EXCERPTS},
    }
    (HERE / "facts.json").write_text(json.dumps(facts, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote facts.json: {len(facts['labels'])} labels, {len(facts['code'])} code excerpts, delays {delays}")


if __name__ == "__main__":
    main()
