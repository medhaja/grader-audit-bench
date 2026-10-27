"""Graders return {"score": 0|1, "reason": str}. Each takes (task, output_text, ctx)."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# Simulated "wall clock" for a grading run. Real graders read datetime.now(); here the clock is derived
# from the run seed so time-dependent (flaky) behaviour is reproducible.
BASE_NOW = datetime(2025, 6, 1, 10, 15, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class GradeContext:
    seed: int
    now: datetime

    @classmethod
    def for_seed(cls, seed: int) -> "GradeContext":
        # A grading job starts somewhere between 0 and 10 minutes after the agent finished.
        delay = random.Random(seed).uniform(0, 600)
        return cls(seed=seed, now=BASE_NOW + timedelta(seconds=delay))


def verdict(score: bool, reason: str, **extra) -> dict:
    return {"score": int(bool(score)), "reason": reason, **extra}
