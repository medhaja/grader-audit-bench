"""Write the synthetic benchmark (12 tasks) and 96 labeled probe outputs to data/.

Usage: python -m audit.generate [--out data]
Output is byte-for-byte deterministic for a given seed.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from . import DATA_DIR
from .probes import EXT, PROBES, build_probes
from .tasks import SEED, build_tasks

SPEC_SKIP = {"inputs", "gold"}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def generate(out_dir: Path = DATA_DIR, seed: int = SEED) -> Path:
    out_dir = Path(out_dir)
    for sub in ("tasks", "probes"):
        shutil.rmtree(out_dir / sub, ignore_errors=True)

    labels = []
    for task in build_tasks(seed):
        tdir = out_dir / "tasks" / task["id"]
        ext = EXT[task["type"]]
        spec = {k: v for k, v in task.items() if k not in SPEC_SKIP}
        spec["input_files"] = list(task["inputs"])
        spec["gold_file"] = f"gold.{ext}"
        _write(tdir / "task.json", json.dumps(spec, indent=2, ensure_ascii=False) + "\n")
        for name, text in task["inputs"].items():
            _write(tdir / "inputs" / name, text)
        _write(tdir / f"gold.{ext}", task["gold"])

        for probe, (output, should_pass) in build_probes(task, seed).items():
            rel = f"probes/{task['id']}/{probe}.{ext}"
            _write(out_dir / rel, output)
            labels.append({"task_id": task["id"], "probe": probe, "should_pass": should_pass, "output_file": rel})

    _write(out_dir / "labels.json", json.dumps(labels, indent=2) + "\n")
    return out_dir


def load_tasks(data_dir: Path = DATA_DIR) -> list[dict]:
    """Read tasks back from disk. Returns spec dicts with `inputs` and `gold` text attached."""
    tasks = []
    for tdir in sorted((Path(data_dir) / "tasks").iterdir()):
        spec = json.loads((tdir / "task.json").read_text(encoding="utf-8"))
        spec["inputs"] = {n: _read(tdir / "inputs" / n) for n in spec["input_files"]}
        spec["gold"] = _read(tdir / spec["gold_file"])
        tasks.append(spec)
    return tasks


def load_cases(data_dir: Path = DATA_DIR) -> list[dict]:
    """Return labeled probe cases: task_id, probe, should_pass, output."""
    data_dir = Path(data_dir)
    labels = json.loads((data_dir / "labels.json").read_text(encoding="utf-8"))
    for case in labels:
        case["output"] = _read(data_dir / case["output_file"])
    return labels


def _read(path: Path) -> str:
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DATA_DIR)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    out = generate(args.out, args.seed)
    n = len(json.loads((out / "labels.json").read_text(encoding="utf-8")))
    print(f"Wrote 12 tasks and {n} labeled probe outputs to {out}")


if __name__ == "__main__":
    main()
