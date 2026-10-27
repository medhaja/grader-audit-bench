"""Hardened graders: typed normalization, real data equality, invariants. No trust in "done" flags.

- answer: exact match after normalization; if that fails, ask the semantic judge (mock or LLM).
- table:  parse CSV, normalize headers/cells by declared column type (Unicode NFC, null tokens, float
          tolerance, date formats), then check row count, key uniqueness and row equality
          (order-insensitive unless the task says order matters).
- state:  parse JSON, require the same field set as gold, compare each field by declared type.
"""

from __future__ import annotations

import io
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone

import pandas as pd

from . import GradeContext, verdict
from . import judge as judge_mod

NULL_TOKENS = {"", "null", "none", "nan", "n/a"}
DATE_FORMATS = ["%Y-%m-%d", "%Y/%m/%d"]  # MM/DD vs DD/MM is ambiguous, so neither is accepted


class GradeError(ValueError):
    """Raised when an output cannot be normalized; the message is the grader's reason."""


# ---- shared normalizers -----------------------------------------------------------------

def normalize_text(s: str) -> str:
    s = unicodedata.normalize("NFC", s).lower()
    s = re.sub(r"[^\w.]+", " ", s)
    return " ".join(s.split()).strip(" .")


def _exact(gold_norm: str, out_norm: str) -> bool:
    return gold_norm == out_norm


def parse_date(v: str) -> str:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt).date().isoformat()
        except ValueError:
            pass
    raise GradeError(f"cannot parse '{v}' as a date (expected YYYY-MM-DD)")


def parse_datetime(v: str) -> str:
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        raise GradeError(f"cannot parse '{v}' as a datetime") from None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat()


def normalize_cell(value: str, col_type: str):
    v = unicodedata.normalize("NFC", str(value)).strip()
    if v.lower() in NULL_TOKENS:
        return None
    try:
        if col_type == "float":
            return repr(round(float(v.replace(",", "")), 6))  # 1.50, 1.5 and 1.5000001 -> "1.5"
        if col_type == "int":
            f = float(v)
            if not f.is_integer():
                raise ValueError
            return str(int(f))
    except ValueError:
        raise GradeError(f"cannot parse '{v}' as {col_type}") from None
    if col_type == "date":
        return parse_date(v)
    if col_type == "datetime":
        return parse_datetime(v)
    return v


# ---- answer -----------------------------------------------------------------------------

def grade_answer(task: dict, output: str, ctx: GradeContext, judge=None) -> dict:
    if _exact(normalize_text(task["gold"]), normalize_text(output)):
        return verdict(True, "exact match after normalization", graded_by="exact")
    judge = judge or judge_mod.get_judge()
    result = judge.judge(task, output)
    return verdict(result["score"], f"judge ({judge.name}): {result['reason']}", graded_by="judge",
                   judge={"backend": judge.name, **result})


# ---- table ------------------------------------------------------------------------------

def normalize_table(task: dict, text: str) -> list[tuple]:
    """Parse and normalize a CSV output into row tuples in schema column order."""
    schema = task["schema"]
    if not text.strip():
        raise GradeError("output is empty")
    try:
        df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False, skipinitialspace=True)
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as e:
        raise GradeError(f"output is not valid CSV: {e}") from None
    df.columns = [unicodedata.normalize("NFC", str(c)).strip().lower() for c in df.columns]
    cols = list(df.columns)
    if len(set(cols)) != len(cols):
        raise GradeError("duplicate column names")
    missing, extra = set(schema) - set(cols), set(cols) - set(schema)
    if missing or extra:
        raise GradeError(f"columns differ: missing {sorted(missing)}, unexpected {sorted(extra)}")
    rows = []
    for i, rec in enumerate(df[list(schema)].itertuples(index=False), start=1):
        try:
            rows.append(tuple(normalize_cell(v, schema[c]) for c, v in zip(schema, rec)))
        except GradeError as e:
            raise GradeError(f"row {i}: {e}") from None
    return rows


def _sort_key(row: tuple) -> tuple:
    return tuple("" if v is None else v for v in row)


def grade_table(task: dict, output: str, ctx: GradeContext) -> dict:
    try:
        gold = normalize_table(task, task["gold"])
        rows = normalize_table(task, output)
    except GradeError as e:
        return verdict(False, str(e))
    if not rows:
        return verdict(False, "no data rows")
    if len(rows) != len(gold):
        return verdict(False, f"row count {len(rows)} != expected {len(gold)}")

    cols = list(task["schema"])
    key_idx = [cols.index(k) for k in task.get("key", [])]
    if key_idx:
        dupes = [k for k, n in Counter(tuple(r[i] for i in key_idx) for r in rows).items() if n > 1]
        if dupes:
            return verdict(False, f"duplicate key {dupes[0]}")

    if not task["order_matters"]:
        rows, gold = sorted(rows, key=_sort_key), sorted(gold, key=_sort_key)
    for i, (got, want) in enumerate(zip(rows, gold), start=1):
        if got != want:
            diffs = [f"{c}: expected {w!r}, got {g!r}" for c, g, w in zip(cols, got, want) if g != w]
            where = f"row {i}" if task["order_matters"] else "a row"
            return verdict(False, f"{where} differs ({'; '.join(diffs[:2])})")
    order = "in order" if task["order_matters"] else "order-insensitive"
    return verdict(True, f"all {len(rows)} rows match gold ({order}, typed comparison)")


def table_diff(task: dict, output: str) -> dict:
    """Rows only in the output vs only in gold, after normalization. Used by the case view."""
    try:
        gold = normalize_table(task, task["gold"])
        rows = normalize_table(task, output)
    except GradeError as e:
        return {"columns": list(task["schema"]), "error": str(e), "only_in_output": [], "only_in_gold": []}
    got, want = Counter(rows), Counter(gold)
    return {
        "columns": list(task["schema"]),
        "error": None,
        "only_in_output": [list(r) for r in (got - want).elements()],
        "only_in_gold": [list(r) for r in (want - got).elements()],
        "order_differs": task["order_matters"] and not (got - want) and not (want - got) and rows != gold,
    }


# ---- state ------------------------------------------------------------------------------

def normalize_field(value, field_type: str):
    if value is None:
        return None
    if field_type == "enum":
        return str(value).strip().lower()
    if field_type == "int":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or float(value) != int(value):
            raise GradeError(f"expected an integer, got {value!r}")
        return int(value)
    if field_type == "datetime":
        return parse_datetime(str(value))
    if field_type == "date":
        return parse_date(str(value))
    if field_type == "unordered_list":
        if not isinstance(value, list):
            raise GradeError(f"expected a list, got {value!r}")
        return sorted(map(str, value))
    return unicodedata.normalize("NFC", str(value)).strip()


def grade_state(task: dict, output: str, ctx: GradeContext) -> dict:
    try:
        record = json.loads(output)
    except json.JSONDecodeError:
        return verdict(False, "output is not valid JSON")
    if not isinstance(record, dict):
        return verdict(False, "output is not a JSON object")
    gold = json.loads(task["gold"])
    missing, extra = set(gold) - set(record), set(record) - set(gold)
    if missing or extra:
        return verdict(False, f"fields differ: missing {sorted(missing)}, unexpected {sorted(extra)}")
    for field, field_type in task["fields"].items():
        try:
            got = normalize_field(record[field], field_type)
        except GradeError as e:
            return verdict(False, f"{field}: {e}")
        want = normalize_field(gold[field], field_type)
        if got != want:
            return verdict(False, f"{field}: expected {want!r}, got {got!r}")
    return verdict(True, f"all {len(gold)} fields match gold (typed comparison)")


GRADERS = {"answer": grade_answer, "table": grade_table, "state": grade_state}


def grade(task: dict, output: str, ctx: GradeContext, judge=None) -> dict:
    if task["type"] == "answer":
        return grade_answer(task, output, ctx, judge=judge)
    return GRADERS[task["type"]](task, output, ctx)
