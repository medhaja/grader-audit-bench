"""Audit runner: grade every labeled probe K times per grader, compute error rates, write reports.

Usage: python -m audit.runner [--k 5]   (expects data/ from `python -m audit.generate`)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import DATA_DIR, RESULTS_DIR
from .generate import load_cases, load_tasks
from .graders import GradeContext, hardened, naive
from .graders import judge as judge_mod
from .probes import PROBE_DESCRIPTIONS, PROBES

GRADER_NAMES = ["naive", "hardened"]
SNIPPET_CHARS = 240


def snippet(text: str, n: int = SNIPPET_CHARS) -> str:
    text = text.replace("\r\n", "\n")
    return text if len(text) <= n else text[:n] + " …"


def _grade_k(grade_fn, task: dict, output: str, k: int) -> dict:
    runs = [grade_fn(task, output, GradeContext.for_seed(seed)) for seed in range(k)]
    scores = [r["score"] for r in runs]
    majority = int(sum(scores) * 2 > k)
    first = next(r for r in runs if r["score"] == majority)
    return {
        "score": majority,
        "runs": scores,
        "flaky": len(set(scores)) > 1,
        "reason": first["reason"],
        "graded_by": first.get("graded_by"),
        "judge": first.get("judge"),
    }


def run_audit(data_dir: Path = DATA_DIR, k: int = 5, judge=None, graders: dict | None = None) -> dict:
    judge = judge or judge_mod.get_judge()
    graders = graders or {
        "naive": naive.grade,
        "hardened": lambda t, o, ctx: hardened.grade(t, o, ctx, judge=judge),
    }
    tasks = {t["id"]: t for t in load_tasks(data_dir)}
    cases, outputs = [], {}
    for case in load_cases(data_dir):
        outputs[(case["task_id"], case["probe"])] = case["output"]
        task = tasks[case["task_id"]]
        verdicts = {}
        for name, fn in graders.items():
            v = _grade_k(fn, task, case["output"], k)
            v["error"] = ("FP" if v["score"] and not case["should_pass"]
                          else "FN" if not v["score"] and case["should_pass"] else None)
            verdicts[name] = v
        cases.append({
            "task_id": task["id"], "task_type": task["type"], "probe": case["probe"],
            "should_pass": case["should_pass"], "output_snippet": snippet(case["output"]),
            "verdicts": verdicts,
        })

    summary = {name: _summarize(cases, name) for name in graders}
    matrix = {
        probe: {name: _cell(cases, probe, name) for name in graders} for probe in PROBES
    }
    per_task = [
        {"task_id": tid, "type": t["type"],
         **{f"{name}_errors": sum(1 for c in cases if c["task_id"] == tid and c["verdicts"][name]["error"])
            for name in graders},
         **{f"{name}_flaky": sum(1 for c in cases if c["task_id"] == tid and c["verdicts"][name]["flaky"])
            for name in graders}}
        for tid, t in tasks.items()
    ]
    return {
        "meta": {"k": k, "seeds": list(range(k)), "judge_backend": judge.name, "n_tasks": len(tasks),
                 "n_cases": len(cases), "graders": list(graders), "probes": PROBES,
                 "probe_descriptions": PROBE_DESCRIPTIONS},
        "summary": summary,
        "headline": _headline(summary, matrix, len(tasks)),
        "matrix": matrix,
        "per_task": per_task,
        "cases": cases,
        "judge": _judge_section(cases, tasks, outputs, judge),
    }


def _summarize(cases: list[dict], name: str) -> dict:
    pos = [c for c in cases if c["should_pass"]]
    neg = [c for c in cases if not c["should_pass"]]
    fp = sum(c["verdicts"][name]["error"] == "FP" for c in cases)
    fn = sum(c["verdicts"][name]["error"] == "FN" for c in cases)
    flaky = sum(c["verdicts"][name]["flaky"] for c in cases)
    return {
        "fp": fp, "fn": fn, "flaky": flaky, "negatives": len(neg), "positives": len(pos), "total": len(cases),
        "fp_rate": fp / len(neg) if neg else 0.0,
        "fn_rate": fn / len(pos) if pos else 0.0,
        "flaky_rate": flaky / len(cases) if cases else 0.0,
    }


def _cell(cases: list[dict], probe: str, name: str) -> dict:
    sel = [c for c in cases if c["probe"] == probe]
    return {
        "total": len(sel),
        "passed": sum(c["verdicts"][name]["score"] for c in sel),
        "should_pass": sum(c["should_pass"] for c in sel),
        "fp": sum(c["verdicts"][name]["error"] == "FP" for c in sel),
        "fn": sum(c["verdicts"][name]["error"] == "FN" for c in sel),
        "flaky": sum(c["verdicts"][name]["flaky"] for c in sel),
        "wrong": sum(bool(c["verdicts"][name]["error"]) for c in sel),
    }


def _headline(summary: dict, matrix: dict, n_tasks: int) -> str:
    n, h = summary["naive"], summary["hardened"]
    worst = max(PROBES, key=lambda p: matrix[p]["naive"]["fp"])
    worst_fp = matrix[worst]["naive"]["fp"]
    hardened_errors = h["fp"] + h["fn"]
    hardened_part = (f"hardened graders got all {h['total']} right" if hardened_errors == 0
                     else f"hardened graders made {hardened_errors} wrong verdicts")
    return (f"Naive graders passed {worst_fp} of {n_tasks} {worst.replace('_', '-')} agents and "
            f"wrongly failed {n['fn']} of {n['positives']} correct outputs; {hardened_part}.")


def _judge_section(cases: list[dict], tasks: dict, outputs: dict, judge) -> dict:
    """Judge calls made inside hardened grading, plus a standalone check on every answer probe."""
    log = []
    for c in cases:
        j = c["verdicts"].get("hardened", {}).get("judge")
        if j:
            log.append({"task_id": c["task_id"], "probe": c["probe"], "should_pass": c["should_pass"],
                        "score": j["score"], "reason": j["reason"], "agrees": bool(j["score"]) == c["should_pass"]})

    judges = [judge_mod.MockJudge()]
    if judge.name != "mock":
        judges.append(judge)
    evaluation = {}
    for j in judges:
        rows = []
        for c in cases:
            if c["task_type"] != "answer":
                continue
            r = j.judge(tasks[c["task_id"]], outputs[(c["task_id"], c["probe"])])
            rows.append({"task_id": c["task_id"], "probe": c["probe"], "should_pass": c["should_pass"],
                         "score": r["score"], "reason": r["reason"]})
        disagreements = [r for r in rows if bool(r["score"]) != r["should_pass"]]
        evaluation[j.name] = {"agree": len(rows) - len(disagreements), "total": len(rows),
                              "disagreements": disagreements}
    return {"log": log, "evaluation": evaluation}


# ---- reports ----------------------------------------------------------------------------

def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def render_report(results: dict) -> str:
    m, s = results["meta"], results["summary"]
    lines = [
        "# Grader audit report",
        "",
        "_Independent prototype built from public information and synthetic data. Not affiliated with HUD._",
        "",
        f"{m['n_tasks']} synthetic tasks × {len(m['probes'])} probes = {m['n_cases']} labeled cases. "
        f"Each grader ran K={m['k']} times per case (seeds {m['seeds'][0]}–{m['seeds'][-1]}); "
        f"the verdict is the majority. Judge backend: `{m['judge_backend']}`.",
        "",
        f"**{results['headline']}**",
        "",
        "## Summary",
        "",
        "| Grader | False positives | False negatives | Flaky |",
        "|---|---|---|---|",
    ]
    for name in m["graders"]:
        g = s[name]
        lines.append(f"| {name} | {g['fp']}/{g['negatives']} ({pct(g['fp_rate'])}) "
                     f"| {g['fn']}/{g['positives']} ({pct(g['fn_rate'])}) "
                     f"| {g['flaky']}/{g['total']} ({pct(g['flaky_rate'])}) |")
    lines += ["", "## Probe × grader", "",
              "Cells show wrong verdicts out of 12 tasks (FP / FN), and how many were flaky.", "",
              "| Probe | Should pass | " + " | ".join(m["graders"]) + " |",
              "|---|---|" + "---|" * len(m["graders"])]
    for probe in m["probes"]:
        row = results["matrix"][probe]
        first = row[m["graders"][0]]
        cells = []
        for name in m["graders"]:
            c = row[name]
            cell = f"{c['wrong']} wrong ({c['fp']} FP / {c['fn']} FN)" if c["wrong"] else "0"
            if c["flaky"]:
                cell += f", {c['flaky']} flaky"
            cells.append(cell)
        lines.append(f"| `{probe}` | {first['should_pass']}/{first['total']} | " + " | ".join(cells) + " |")

    lines += ["", "## Per task", "", "| Task | Type | " + " | ".join(f"{n} errors" for n in m["graders"])
              + " | Flaky (naive) |", "|---|---|" + "---|" * (len(m["graders"]) + 1)]
    for t in results["per_task"]:
        lines.append(f"| `{t['task_id']}` | {t['type']} | "
                     + " | ".join(str(t[f"{n}_errors"]) for n in m["graders"])
                     + f" | {t.get('naive_flaky', 0)} |")

    lines += ["", "## Every wrong verdict", ""]
    any_wrong = False
    for name in m["graders"]:
        wrong = [c for c in results["cases"] if c["verdicts"][name]["error"]]
        lines += [f"### {name} ({len(wrong)})", ""]
        if not wrong:
            lines += ["None.", ""]
            continue
        any_wrong = True
        for c in wrong:
            v = c["verdicts"][name]
            flaky = f" · flaky, runs={v['runs']}" if v["flaky"] else ""
            lines += [
                f"- **{v['error']}** · `{c['task_id']}` · probe `{c['probe']}` "
                f"(should {'pass' if c['should_pass'] else 'fail'}){flaky}",
                f"  - Grader reason: {v['reason']}",
                "  - Output snippet:",
                "",
                "    ```",
                *["    " + ln for ln in c["output_snippet"].splitlines()[:6] or ["(empty)"]],
                "    ```",
                "",
            ]
    if not any_wrong:
        lines += ["No wrong verdicts.", ""]

    lines += ["## Flaky verdicts", ""]
    flaky = [(c, n) for c in results["cases"] for n in m["graders"] if c["verdicts"][n]["flaky"]]
    if flaky:
        lines += ["| Task | Probe | Grader | Runs |", "|---|---|---|---|"]
        lines += [f"| `{c['task_id']}` | `{c['probe']}` | {n} | {c['verdicts'][n]['runs']} |" for c, n in flaky]
    else:
        lines.append("None.")

    j = results["judge"]
    lines += ["", "## Semantic judge", "",
              f"The hardened answer grader called the judge {len(j['log'])} times (exact check failed). "
              f"{sum(e['agrees'] for e in j['log'])} of those verdicts agree with the label.", ""]
    for backend, ev in j["evaluation"].items():
        lines.append(f"- Standalone check, `{backend}` judge on all answer probes: "
                     f"{ev['agree']}/{ev['total']} agree with labels.")
        for d in ev["disagreements"]:
            lines.append(f"  - Disagrees: `{d['task_id']}` / `{d['probe']}` "
                         f"(should {'pass' if d['should_pass'] else 'fail'}): {d['reason']}")
    lines.append("")
    return "\n".join(lines)


def write_results(results: dict, out_dir: Path = RESULTS_DIR) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "results.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(results, f, indent=1, ensure_ascii=False)
        f.write("\n")
    with open(out_dir / "report.md", "w", encoding="utf-8", newline="\n") as f:
        f.write(render_report(results))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, default=5, help="repeats per grader per case (flakiness check)")
    parser.add_argument("--data", type=Path, default=DATA_DIR)
    parser.add_argument("--out", type=Path, default=RESULTS_DIR)
    args = parser.parse_args()
    results = run_audit(args.data, k=args.k)
    write_results(results, args.out)
    for name, g in results["summary"].items():
        print(f"{name:9s} FP {g['fp']:2d}/{g['negatives']} ({pct(g['fp_rate'])})  "
              f"FN {g['fn']:2d}/{g['positives']} ({pct(g['fn_rate'])})  "
              f"flaky {g['flaky']:2d}/{g['total']} ({pct(g['flaky_rate'])})")
    print(results["headline"])
    print(f"Wrote {args.out / 'results.json'} and {args.out / 'report.md'}")


if __name__ == "__main__":
    main()
