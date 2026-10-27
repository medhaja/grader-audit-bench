"""One-command demo: generate data, run the audit, serve the UI.

Usage: python -m audit.serve [--port 8000] [--k 5]
"""

from __future__ import annotations

import argparse
import json

import markdown
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response

from . import DATA_DIR, RESULTS_DIR, ROOT
from .generate import generate, load_cases, load_tasks
from .graders import hardened
from .runner import render_report, run_audit, write_results

STATIC = ROOT / "static"
app = FastAPI(title="Grader Audit")
_state: dict = {}


def prepare(k: int = 5) -> dict:
    """Regenerate data, rerun the audit and cache everything the API serves."""
    generate(DATA_DIR)
    results = run_audit(DATA_DIR, k=k)
    write_results(results, RESULTS_DIR)
    _load(results)
    return results


def _load(results: dict) -> None:
    _state["results"] = results
    _state["tasks"] = {t["id"]: t for t in load_tasks(DATA_DIR)}
    _state["outputs"] = {(c["task_id"], c["probe"]): c["output"] for c in load_cases(DATA_DIR)}
    _state["report"] = render_report(results)


def _ensure_loaded() -> None:
    if "results" not in _state:
        path = RESULTS_DIR / "results.json"
        if path.exists():
            _load(json.loads(path.read_text(encoding="utf-8")))
        else:
            prepare()


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/results")
def results():
    _ensure_loaded()
    return _state["results"]


@app.get("/api/case/{task_id}/{probe}")
def case(task_id: str, probe: str):
    _ensure_loaded()
    match = next((c for c in _state["results"]["cases"]
                  if c["task_id"] == task_id and c["probe"] == probe), None)
    if match is None:
        raise HTTPException(404, "unknown task or probe")
    task = _state["tasks"][task_id]
    output = _state["outputs"][(task_id, probe)]
    return {
        **match,
        "instruction": task["instruction"],
        "input_files": task["input_files"],
        "output": output,
        "gold": task["gold"],
        "diff": hardened.table_diff(task, output) if task["type"] == "table" else None,
        "order_matters": task.get("order_matters"),
    }


@app.get("/api/report")
def report():
    _ensure_loaded()
    md = _state["report"]
    return {"markdown": md, "html": markdown.markdown(md, extensions=["tables", "fenced_code"])}


@app.get("/report.md", include_in_schema=False)
def report_download():
    _ensure_loaded()
    return Response(_state["report"], media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="grader-audit-report.md"'})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    import uvicorn

    results = prepare(args.k)
    for name, s in results["summary"].items():
        print(f"  {name:9s} FP {s['fp']}/{s['negatives']}  FN {s['fn']}/{s['positives']}  flaky {s['flaky']}/{s['total']}")
    print(f"  {results['headline']}")
    print(f"\n  Grader Audit UI: http://localhost:{args.port}\n", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
