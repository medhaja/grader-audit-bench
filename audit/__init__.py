"""Grader Audit: measure false positives, false negatives and flakiness in benchmark graders."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
