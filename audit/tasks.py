"""Seeded generator for the synthetic mini-benchmark: 12 data-engineering tasks.

Everything here is synthetic. Names, IDs, amounts and pipeline records are made up.
"""

from __future__ import annotations

import copy
import csv
import io
import json
import random
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

SEED = 1337
REGIONS = ["Central", "North-East", "South", "West"]

# Fictional names, chosen to exercise Unicode handling (accents, NFC vs NFD, near-duplicates).
NAMES = [
    "Asha Rao", "José Álvarez", "Jose Alvarez", "Zoë Müller", "Søren Dahl", "Nguyễn Minh",
    "Ana Lima", "Chen Wei", "Priya Nair", "Omar Haddad", "Łukasz Nowak", "Fatima Zahra",
    "Kenji Sato", "Ingrid Berg", "Ravi Kumar", "Maria Rossi", "Ébène Diallo", "Tomás Ruiz",
    "Aiko Tanaka", "Dmitri Volkov", "Noor Khan", "Björn Ek", "Lucía Gómez", "Femi Adeyemi",
    "Hana Kim", "Mateo Silva", "Elif Şahin", "Arjun Mehta", "Chloé Martin", "Kwame Mensah",
]

ORDERS_HEADER = ["order_id", "customer_id", "amount", "order_date", "status"]
CUSTOMERS_HEADER = ["customer_id", "name", "region", "updated_at"]


def to_csv(header: list[str], rows: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=header, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: ("" if row[k] is None else row[k]) for k in header})
    return buf.getvalue()


def to_json(record: dict) -> str:
    return json.dumps(record, indent=2, ensure_ascii=False) + "\n"


def _base_data(rng: random.Random):
    customers = []
    for i, name in enumerate(NAMES, start=1):
        updated = datetime(2025, 5, 1, 8, 0) + timedelta(minutes=rng.randint(0, 60 * 24 * 20))
        customers.append({
            "customer_id": f"C{i:03d}",
            "name": name,
            "region": rng.choice(REGIONS),
            "updated_at": updated.isoformat(),
        })

    # Raw customers: 8 stale duplicates with older timestamps and an outdated region.
    raw = [dict(c) for c in customers]
    for c in rng.sample(customers, 8):
        stale = dict(c)
        stale["region"] = rng.choice([r for r in REGIONS if r != c["region"]])
        stale["updated_at"] = (datetime.fromisoformat(c["updated_at"]) - timedelta(days=rng.randint(3, 40))).isoformat()
        raw.append(stale)
    rng.shuffle(raw)

    # Orders: 120 rows, exactly 7 with a null customer_id (one forced into the first 25 rows).
    n_orders = 120
    null_idx = set(rng.sample(range(25, n_orders), 6)) | {3}
    ordering_customers = [c["customer_id"] for c in customers[:28]]  # C029, C030 never order
    orders = []
    for i in range(n_orders):
        orders.append({
            "order_id": f"O{i + 1:04d}",
            "customer_id": None if i in null_idx else rng.choice(ordering_customers),
            "amount": round(rng.uniform(5, 250), 2),
            "order_date": (date(2025, 5, 1) + timedelta(days=rng.randint(0, 30))).isoformat(),
            "status": rng.choices(["completed", "cancelled", "pending"], weights=[7, 2, 1])[0],
        })

    # Make the completed total end in a 0 so "1234.50" vs "1234.5" is a real format variant.
    completed = [o for o in orders if o["status"] == "completed"]
    cents = round(sum(o["amount"] for o in completed) * 100)
    if cents % 10:
        completed[-1]["amount"] = round(completed[-1]["amount"] + (10 - cents % 10) / 100, 2)
    return customers, raw, orders


def _fmt_orders(orders: list[dict]) -> list[dict]:
    return [{**o, "amount": f"{o['amount']:.2f}"} for o in orders]


def build_tasks(seed: int = SEED) -> list[dict]:
    """Return 12 task dicts. Each has spec fields, `inputs` {filename: text} and `gold` text."""
    rng = random.Random(seed)
    customers, customers_raw, orders = _base_data(rng)
    cust_by_id = {c["customer_id"]: c for c in customers}
    completed = [o for o in orders if o["status"] == "completed"]
    orders_csv = to_csv(ORDERS_HEADER, _fmt_orders(orders))
    customers_csv = to_csv(CUSTOMERS_HEADER, customers)

    region_totals: dict[str, float] = defaultdict(float)
    region_counts: Counter = Counter()
    for o in completed:
        if o["customer_id"]:
            region = cust_by_id[o["customer_id"]]["region"]
            region_totals[region] += o["amount"]
            region_counts[region] += 1
    regions_ranked = sorted(region_totals, key=region_totals.get, reverse=True)

    cust_totals: dict[str, float] = defaultdict(float)
    for o in completed:
        if o["customer_id"]:
            cust_totals[o["customer_id"]] += o["amount"]
    top5 = sorted(cust_totals, key=cust_totals.get, reverse=True)[:5]

    total_revenue = sum(o["amount"] for o in completed)
    n_null = sum(1 for o in orders if o["customer_id"] is None)
    n_distinct = len({o["customer_id"] for o in orders if o["customer_id"]})

    tasks: list[dict] = []

    # ---- answer tasks -------------------------------------------------------------------
    tasks.append({
        "id": "A1_null_customer_ids", "type": "answer", "answer_kind": "numeric",
        "instruction": "How many rows in orders.csv have a null (empty) customer_id? Answer with the number.",
        "inputs": {"orders.csv": orders_csv}, "gold": str(n_null),
    })
    tasks.append({
        "id": "A2_completed_revenue", "type": "answer", "answer_kind": "numeric",
        "instruction": "What is the total amount of orders with status 'completed' in orders.csv? Give two decimals.",
        "inputs": {"orders.csv": orders_csv}, "gold": f"{total_revenue:.2f}",
    })
    tasks.append({
        "id": "A3_top_region", "type": "answer", "answer_kind": "text",
        "instruction": "Join orders.csv to customers.csv. Which region has the highest total completed order amount?",
        "inputs": {"orders.csv": orders_csv, "customers.csv": customers_csv}, "gold": regions_ranked[0],
        "runner_up": regions_ranked[1],
    })
    tasks.append({
        "id": "A4_distinct_customers", "type": "answer", "answer_kind": "numeric",
        "instruction": "How many distinct customers (non-null customer_id) placed at least one order in orders.csv?",
        "inputs": {"orders.csv": orders_csv}, "gold": str(n_distinct),
    })

    # ---- table tasks --------------------------------------------------------------------
    tasks.append({
        "id": "T1_dedupe_customers", "type": "table",
        "instruction": "customers_raw.csv has duplicate customer_id rows. Keep only the row with the latest "
                       "updated_at per customer_id. Output columns: customer_id,name,region,updated_at.",
        "inputs": {"customers_raw.csv": to_csv(CUSTOMERS_HEADER, customers_raw)},
        "schema": {"customer_id": "str", "name": "str", "region": "str", "updated_at": "datetime"},
        "key": ["customer_id"], "order_matters": False,
        "gold": customers_csv,
    })

    joined = [{"order_id": o["order_id"], "customer_name": cust_by_id[o["customer_id"]]["name"],
               "amount": f"{o['amount']:.2f}"} for o in orders if o["customer_id"]]
    tasks.append({
        "id": "T2_join_orders_customers", "type": "table",
        "instruction": "Inner-join orders.csv to customers.csv on customer_id. Output columns: "
                       "order_id,customer_name,amount. Drop orders with a null customer_id.",
        "inputs": {"orders.csv": orders_csv, "customers.csv": customers_csv},
        "schema": {"order_id": "str", "customer_name": "str", "amount": "float"},
        "key": ["order_id"], "order_matters": False,
        "gold": to_csv(["order_id", "customer_name", "amount"], joined),
    })

    # Type-cast task: messy raw values, same header and row count as the gold output.
    cast_header = ["order_id", "customer_id", "amount", "order_date"]
    raw_rows, gold_rows = [], []
    null_tokens = ["", "NULL", "null"]
    for i, o in enumerate(orders[:25]):
        d = date.fromisoformat(o["order_date"])
        amt = o["amount"]
        raw_amount = [f" {amt} ", f"{amt:.2f}", f"{amt:.3f}"][i % 3]
        raw_rows.append({
            "order_id": o["order_id"],
            "customer_id": o["customer_id"] or null_tokens[i % 3],
            "amount": raw_amount,
            "order_date": d.strftime("%m/%d/%Y"),
        })
        gold_rows.append({"order_id": o["order_id"], "customer_id": o["customer_id"],
                          "amount": f"{amt:.2f}", "order_date": d.isoformat()})
    tasks.append({
        "id": "T3_cast_types", "type": "table",
        "instruction": "orders_raw.csv has messy types. Cast amount to a 2-decimal number, order_date "
                       "(MM/DD/YYYY) to ISO YYYY-MM-DD, and NULL/null/empty customer_id to empty. Keep column order.",
        "inputs": {"orders_raw.csv": to_csv(cast_header, raw_rows)},
        "schema": {"order_id": "str", "customer_id": "str", "amount": "float", "order_date": "date"},
        "key": ["order_id"], "order_matters": False,
        "gold": to_csv(cast_header, gold_rows),
    })

    agg_rows = [{"region": r, "total_amount": f"{region_totals[r]:.2f}", "order_count": region_counts[r]}
                for r in sorted(region_totals)]
    tasks.append({
        "id": "T4_revenue_by_region", "type": "table",
        "instruction": "Join orders.csv to customers.csv and aggregate completed orders by region. Output "
                       "columns: region,total_amount,order_count. Ignore orders with a null customer_id.",
        "inputs": {"orders.csv": orders_csv, "customers.csv": customers_csv},
        "schema": {"region": "str", "total_amount": "float", "order_count": "int"},
        "key": ["region"], "order_matters": False,
        "gold": to_csv(["region", "total_amount", "order_count"], agg_rows),
    })

    top_rows = [{"customer_id": cid, "customer_name": cust_by_id[cid]["name"],
                 "total_amount": f"{cust_totals[cid]:.2f}"} for cid in top5]
    tasks.append({
        "id": "T5_top_customers", "type": "table",
        "instruction": "List the top 5 customers by total completed order amount, sorted from highest to "
                       "lowest. Output columns: customer_id,customer_name,total_amount. Row order matters.",
        "inputs": {"orders.csv": orders_csv, "customers.csv": customers_csv},
        "schema": {"customer_id": "str", "customer_name": "str", "total_amount": "float"},
        "key": ["customer_id"], "order_matters": True,
        "gold": to_csv(["customer_id", "customer_name", "total_amount"], top_rows),
    })

    # ---- state tasks --------------------------------------------------------------------
    state_fields = {
        "run_id": "str", "pipeline": "str", "status": "enum", "started_at": "datetime",
        "finished_at": "datetime", "rows_written": "int", "attempt": "int", "error": "str",
        "outputs": "unordered_list",
    }
    run1 = {"run_id": "run-0142", "pipeline": "adf_copy_orders", "status": "running",
            "started_at": "2025-06-01T10:02:11Z", "finished_at": None, "rows_written": None,
            "attempt": 1, "error": None, "outputs": ["bronze.orders", "silver.orders"]}
    gold1 = {**copy.deepcopy(run1), "status": "succeeded", "finished_at": "2025-06-01T10:15:00Z",
             "rows_written": len(orders)}
    tasks.append({
        "id": "S1_finalize_run", "type": "state", "target_status": "succeeded", "fields": state_fields,
        "instruction": "The copy activity finished at 2025-06-01T10:15:00Z. Update run.json: set status to "
                       "'succeeded', finished_at to that time, and rows_written to the number of data rows "
                       "in orders.csv.",
        "inputs": {"run.json": to_json(run1), "orders.csv": orders_csv}, "gold": to_json(gold1),
        "partial_field": ["rows_written", len(orders) - 1],
        # The planted flaky grader: naive check that finished_at is "recent" against the clock.
        "naive_freshness_seconds": 300,
    })

    run2 = {"run_id": "run-0143", "pipeline": "adf_copy_customers", "status": "failed",
            "started_at": "2025-06-01T11:00:00Z", "finished_at": "2025-06-01T11:04:30Z", "rows_written": 0,
            "attempt": 1, "error": "Timeout copying bronze.customers",
            "outputs": ["bronze.customers", "silver.customers"]}
    gold2 = {**copy.deepcopy(run2), "status": "queued", "finished_at": None, "attempt": 2, "error": None}
    tasks.append({
        "id": "S2_requeue_failed_run", "type": "state", "target_status": "queued", "fields": state_fields,
        "instruction": "Re-queue the failed run in run.json: status 'queued', increment attempt by 1, and "
                       "clear error and finished_at (null). Leave every other field as it is.",
        "inputs": {"run.json": to_json(run2)}, "gold": to_json(gold2),
        "partial_field": ["attempt", 1],
    })

    max_date = max(o["order_date"] for o in orders)
    run3 = {"run_id": "run-0144", "pipeline": "adf_incremental_orders", "status": "running",
            "started_at": "2025-06-02T02:00:00Z", "last_watermark": "2025-04-30",
            "outputs": ["silver.orders", "gold.daily_revenue"]}
    gold3 = {**copy.deepcopy(run3), "status": "succeeded", "last_watermark": max_date}
    wm_fields = {"run_id": "str", "pipeline": "str", "status": "enum", "started_at": "datetime",
                 "last_watermark": "date", "outputs": "unordered_list"}
    tasks.append({
        "id": "S3_advance_watermark", "type": "state", "target_status": "succeeded", "fields": wm_fields,
        "instruction": "Incremental load done. In run.json set last_watermark to the latest order_date in "
                       "orders.csv (YYYY-MM-DD) and status to 'succeeded'.",
        "inputs": {"run.json": to_json(run3), "orders.csv": orders_csv}, "gold": to_json(gold3),
        "partial_field": ["last_watermark", (date.fromisoformat(max_date) - timedelta(days=1)).isoformat()],
    })
    return tasks
