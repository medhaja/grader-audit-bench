"""End-to-end integration: run the real CLI commands in subprocesses against a temp directory."""

import json
import subprocess
import sys

import pytest

from audit import RESULTS_DIR, ROOT

pytestmark = pytest.mark.integration


def run(*args):
    proc = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", env={"PYTHONIOENCODING": "utf-8", **_base_env()})
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def _base_env():
    import os
    env = dict(os.environ)
    env.pop("JUDGE_MODEL", None)  # always the deterministic mock here
    return env


def test_generate_then_audit_pipeline(tmp_path):
    data, out = tmp_path / "data", tmp_path / "results"
    assert "96 labeled probe outputs" in run("-m", "audit.generate", "--out", str(data))
    assert len(json.loads((data / "labels.json").read_text(encoding="utf-8"))) == 96
    assert len(list((data / "tasks").iterdir())) == 12

    stdout = run("-m", "audit.runner", "--data", str(data), "--out", str(out), "--k", "5")
    assert "hardened  FP  0/49" in stdout

    # A fresh end-to-end run reproduces the committed results exactly.
    for name in ("results.json", "report.md"):
        assert (out / name).read_bytes() == (RESULTS_DIR / name).read_bytes(), name


def test_k1_disables_flakiness_detection(tmp_path):
    data, out = tmp_path / "data", tmp_path / "results"
    run("-m", "audit.generate", "--out", str(data))
    run("-m", "audit.runner", "--data", str(data), "--out", str(out), "--k", "1")
    results = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert results["meta"]["k"] == 1
    assert results["summary"]["naive"]["flaky"] == 0  # one run can never disagree with itself
