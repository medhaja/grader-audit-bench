"""Eight scripted probe agents. Each produces an output for a task with a known true label."""

from __future__ import annotations

import csv
import io
import json
import random
import unicodedata

PROBES = ["gold", "paraphrase", "format_variant", "noop", "substring_trap", "look_done", "shuffled", "partial"]

PROBE_DESCRIPTIONS = {
    "gold": "The exact gold output.",
    "paraphrase": "Same meaning, different wording (sentence answers, header case, NFD Unicode, key order).",
    "format_variant": "Same data, different format (column order, whitespace, 1.50 vs 1.5, date formats).",
    "noop": "Did nothing: empty answer or the input file left untouched.",
    "substring_trap": "Wrong output that contains the right token (e.g. '17' for 7, extra duplicate rows).",
    "look_done": "Looks finished but isn't: 'Done.', a header with no rows, or status: done.",
    "shuffled": "Correct rows or list items in a different order.",
    "partial": "Right schema, one wrong row or field.",
}

EXT = {"answer": "txt", "table": "csv", "state": "json"}


def _parse_csv(text: str) -> tuple[list[str], list[dict]]:
    reader = csv.DictReader(io.StringIO(text))
    return list(reader.fieldnames or []), list(reader)


def _write_csv(header: list[str], rows: list[dict], *, quote_all=False, crlf=False) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n" if crlf else "\n",
                        quoting=csv.QUOTE_ALL if quote_all else csv.QUOTE_MINIMAL)
    writer.writerow(header)
    for row in rows:
        writer.writerow([row[h] for h in header])
    return buf.getvalue()


# ---- answer probes ----------------------------------------------------------------------

def _answer_probes(task: dict) -> dict[str, tuple[str, bool]]:
    gold = task["gold"]
    tid = task["id"]
    if tid == "A1_null_customer_ids":
        # Gold "7" is a substring of the wrong answer "17".
        return {
            "paraphrase": (f"There are {gold} orders with a null customer_id.", True),
            "format_variant": (f"{gold}.0", True),
            "substring_trap": (f"1{gold}", False),
            "shuffled": (f"{gold} is the null customer_id count.", True),
            "partial": (str(int(gold) + 1), False),
        }
    if tid == "A2_completed_revenue":
        value = float(gold)
        return {
            "paraphrase": (f"Completed orders total ${value:,.2f}.", True),
            "format_variant": (gold.rstrip("0").rstrip("."), True),
            "substring_trap": (f"Not {gold}; the corrected total is {value + 100:.2f}.", False),
            "shuffled": (f"{gold} is the completed total.", True),
            "partial": (f"{value + 0.01:.2f}", False),
        }
    if tid == "A3_top_region":
        other = task["runner_up"]
        return {
            "paraphrase": (f"The top region is {gold.lower()}.", True),
            "format_variant": (gold.upper().replace("-", " "), True),
            "substring_trap": (f"Not {gold}, it is {other}.", False),
            "shuffled": (f"{gold} has the highest completed total.", True),
            "partial": (other, False),
        }
    if tid == "A4_distinct_customers":
        return {
            "paraphrase": (f"{gold} distinct customers placed at least one order.", True),
            "format_variant": (f"  {gold}\n", True),
            "substring_trap": (f"Not {gold}; after removing duplicates it is {int(gold) - 1}.", False),
            "shuffled": (f"Distinct ordering customers: {gold}", True),
            "partial": (str(int(gold) - 1), False),
        }
    raise KeyError(tid)


def answer_probe_set(task: dict) -> dict[str, tuple[str, bool]]:
    probes = {
        "gold": (task["gold"], True),
        "noop": ("", False),
        "look_done": ("Done. Task complete.", False),
    }
    probes.update(_answer_probes(task))
    return probes


# ---- table probes -----------------------------------------------------------------------

def _format_value(value: str, col_type: str) -> str:
    if value == "":
        return value
    if col_type == "float":
        return value.rstrip("0").rstrip(".") if "." in value else value
    if col_type == "date":
        return value.replace("-", "/")
    if col_type == "datetime":
        return value.replace("T", " ")
    return value


def table_probe_set(task: dict, rng: random.Random) -> dict[str, tuple[str, bool]]:
    header, rows = _parse_csv(task["gold"])
    schema = task["schema"]
    first_input = next(iter(task["inputs"].values()))

    para_header = [h.upper() for h in header]
    para_rows = [{h.upper(): unicodedata.normalize("NFD", r[h]) for h in header} for r in rows]

    fmt_header = list(reversed(header))
    fmt_rows = [{h: f" {_format_value(r[h], schema[h])} " if r[h] else "" for h in header} for r in rows]

    shuffled = list(rows)
    while shuffled == rows:
        rng.shuffle(shuffled)

    partial_rows = [dict(r) for r in rows]
    victim = rng.randrange(len(rows))
    float_cols = [h for h in header if schema[h] == "float"]
    if float_cols:
        col = float_cols[0]
        partial_rows[victim][col] = f"{float(rows[victim][col]) + 1:.2f}"
    else:
        regions = ["Central", "North-East", "South", "West"]
        partial_rows[victim]["region"] = next(r for r in regions if r != rows[victim]["region"])

    return {
        "gold": (task["gold"], True),
        "paraphrase": (_write_csv(para_header, para_rows, quote_all=True, crlf=True), True),
        "format_variant": (_write_csv(fmt_header, fmt_rows), True),
        "noop": (first_input, False),
        "substring_trap": (_write_csv(header, rows + rows[:3]), False),
        "look_done": (_write_csv(header, []), False),
        "shuffled": (_write_csv(header, shuffled), not task["order_matters"]),
        "partial": (_write_csv(header, partial_rows), False),
    }


# ---- state probes -----------------------------------------------------------------------

def _variant_timestamps(record: dict, fields: dict) -> dict:
    out = dict(record)
    for k, t in fields.items():
        v = out.get(k)
        if v is None:
            continue
        if t == "datetime":
            out[k] = v.replace("Z", "+00:00")
        elif t == "date":
            out[k] = v.replace("-", "/")
        elif t == "int":
            out[k] = float(v)
    return out


def state_probe_set(task: dict) -> dict[str, tuple[str, bool]]:
    gold = json.loads(task["gold"])
    original = json.loads(task["inputs"]["run.json"])
    fields = task["fields"]

    paraphrase = {k: gold[k] for k in reversed(list(gold))}
    paraphrase["status"] = gold["status"].capitalize()
    paraphrase = {k: (v.replace("Z", "+00:00") if fields.get(k) == "datetime" and v else v)
                  for k, v in paraphrase.items()}

    look_done = {**original, "status": "done"}
    trap = {**gold, "status": f"not_{task['target_status']}"}
    shuffled = {**gold, "outputs": list(reversed(gold["outputs"]))}
    field, wrong = task["partial_field"]
    partial = {**gold, field: wrong}

    dump = lambda r: json.dumps(r, indent=2, ensure_ascii=False) + "\n"  # noqa: E731
    return {
        "gold": (task["gold"], True),
        "paraphrase": (json.dumps(paraphrase, indent=4) + "\n", True),
        "format_variant": (json.dumps(_variant_timestamps(gold, fields), separators=(",", ":")), True),
        "noop": (task["inputs"]["run.json"], False),
        "substring_trap": (dump(trap), False),
        "look_done": (dump(look_done), False),
        "shuffled": (dump(shuffled), True),
        "partial": (dump(partial), False),
    }


def build_probes(task: dict, seed: int) -> dict[str, tuple[str, bool]]:
    """Return {probe_name: (output_text, should_pass)} for one task, in PROBES order."""
    if task["type"] == "answer":
        probes = answer_probe_set(task)
    elif task["type"] == "table":
        probes = table_probe_set(task, random.Random(f"{seed}-{task['id']}"))
    else:
        probes = state_probe_set(task)
    return {name: probes[name] for name in PROBES}
