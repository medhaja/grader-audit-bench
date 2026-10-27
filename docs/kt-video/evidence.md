# Evidence for the Grader Audit KT video

Phase 1 record. Every number in the video must trace back to this file and to `snapshot/results.json`.

## 1. Repository state

| Item | Value |
|---|---|
| Commit | `c3dd9a20a375d92ea17d3d82673f0604a569e011` (`c3dd9a2`, branch `main`) |
| Working tree before Phase 1 | clean (`git status --short` empty) |
| Working tree after Phase 1 | new untracked `docs/kt-video/` only. No application code, data, labels or tests changed. |
| `.env` | not present |
| `JUDGE_MODEL` | unset in the shell. Also explicitly removed (`env -u`) for every command below. |
| Python used for the audit | 3.13.5 (system) |

## 2. Exact commands and configuration

All commands were run from the repo root with `JUDGE_MODEL`, `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` removed from the environment:

```bash
env -u JUDGE_MODEL -u ANTHROPIC_API_KEY -u OPENAI_API_KEY python -m audit.generate --out "$TEMP/ga-kt/data"
env -u JUDGE_MODEL -u ANTHROPIC_API_KEY -u OPENAI_API_KEY python -m audit.runner --data "$TEMP/ga-kt/data" --out docs/kt-video/snapshot --k 5
cmp docs/kt-video/snapshot/results.json results/results.json   # identical
cmp docs/kt-video/snapshot/report.md   results/report.md         # identical
diff -r "$TEMP/ga-kt/data" data                                  # identical
```

| Setting | Value | Source |
|---|---|---|
| Data seed | `SEED = 1337` | `audit/tasks.py:16` |
| Repeats per grader per case | `k = 5`, seeds `[0, 1, 2, 3, 4]` | `--k 5`; `results.json → meta.k, meta.seeds` |
| Judge backend | `mock` | `results.json → meta.judge_backend`; selected by `audit/graders/judge.py:91-99` (`JUDGE_MODEL` unset ⇒ `MockJudge`) |

**Frozen snapshot** (the only source of numbers for the video):

| File | SHA-256 |
|---|---|
| `docs/kt-video/snapshot/results.json` | `de8c65a465aa0af86bbad30e434a2394a2f409fc9044c76a062d5505c10eabc0` |
| `docs/kt-video/snapshot/report.md` | `63780be47c65d139f5bb03b0813ab4d0589aa90395cb7f20a40f746547af72a4` |

These match the committed `results/results.json` and `results/report.md` byte for byte.

**Startup command for the UI:** `python -m audit.serve` (or `make demo`, `Makefile:3-4`).

- `prepare()` (`audit/serve.py:25-31`) **regenerates `data/` and reruns the audit** on every start (`serve.py:28-29`), then serves the result.
- For Phase 3, launch it with `JUDGE_MODEL` unset. Before capturing, verify that `/api/results` equals the snapshot.

## 3. Counts (verified from data and snapshot)

| Item | PRD | Implemented / measured | Evidence |
|---|---|---|---|
| Tasks | 12 (4 answer, 5 table, 3 state) | 12: A1–A4 answer, T1–T5 table, S1–S3 state | `audit/tasks.py:123-260`; `meta.n_tasks = 12` |
| Probes | 8 named | same 8 | `audit/probes.py:11` |
| Labeled cases | 96 | 96 (49 `should_pass=false`, 47 `should_pass=true`) | `data/labels.json`; `summary.*.negatives/positives` |
| Positives by type | — | answer 16, table 19, state 12 | snapshot |

The labels are not one uniform pattern per probe. `shuffled` is `should_pass=true` except on `T5_top_customers`, where row order matters (`audit/probes.py:141`, `audit/tasks.py:208-215`). That's why the totals are 47/49, not 48/48.

## 4. Metric definitions (checked in code)

Every grader runs `k = 5` times per case. The runs are aggregated into **one majority verdict per case** before any error is counted: `majority = int(sum(scores) * 2 > k)`, `audit/runner.py:30`. Individual repetitions are **not** counted separately.

| Metric | Definition | Denominator | Code |
|---|---|---|---|
| False positive (FP) | majority score 1 and `should_pass=false` | 49 cases with `should_pass=false` | `runner.py:56`, `runner.py:92, 98` |
| False negative (FN) | majority score 0 and `should_pass=true` | 47 cases with `should_pass=true` | `runner.py:57`, `runner.py:91, 99` |
| Flaky | the 5 per-seed scores are not all equal | 96 distinct cases | `runner.py:35`, `runner.py:100` |

**Consequence of the majority vote:**

- A flaky case counts as FP/FN only if the *majority* is wrong.
- S1 `gold` ran `[0, 1, 0, 1, 1]`, so 2 of 5 runs wrongly failed it. It is flagged flaky but **not** counted as FN.
- S1 `substring_trap` and S1 `partial` (`[0, 1, 0, 1, 1]`) **are** counted as FP, because 3 of 5 runs passed them. Two of the naive grader's 20 FPs therefore depend on this seed draw.

**"Matrix" is not a confusion matrix.**

- The PRD (§FR6) asks for a "probe × grader confusion matrix".
- The implementation is a probe × grader table of **wrong-verdict counts** (FP/FN/flaky per cell): `runner.py:104-114`.
- The UI renders it as a heatmap with alpha proportional to wrong/total: `static/index.html:215-237`, `:230`.
- In the video, call it a "probe-by-grader error heatmap".

## 5. Measured results (snapshot)

Source: `results.json → summary`. The same numbers appear in `report.md § Summary`.

| Grader | FP | FN | Flaky |
|---|---|---|---|
| naive | 20 / 49 (40.8%) | 14 / 47 (29.8%) | 6 / 96 (6.25%, printed 6.2%) |
| hardened | 0 / 49 | 0 / 47 | 0 / 96 |

**Naive errors by probe** (`results.json → matrix.<probe>.naive`, shown as FP / FN / flaky):

| Probe | FP | FN | Flaky |
|---|---|---|---|
| gold | 0 | 0 | 1 |
| paraphrase | 0 | 7 | 1 |
| format_variant | 0 | 7 | 1 |
| noop | 1 | 0 | 0 |
| substring_trap | 7 | 0 | 1 |
| look_done | 3 | 0 | 0 |
| shuffled | 1 | 0 | 1 |
| partial | 8 | 0 | 1 |

Headline string (`results.json → headline`, built by `runner.py:117-125`): "Naive graders passed 8 of 12 partial agents and wrongly failed 14 of 47 correct outputs; hardened graders got all 96 right."

- The headline says "agents". For the video, say "scripted probes".
- **Scope:** the hardened 0/0/0 holds only on these 96 synthetic, hand-written probe cases. The hardened graders were written with these probe types in mind (README "Limitations").

## 6. Selected cases (all from the snapshot)

**False positive: `A1_null_customer_ids × substring_trap`** (`should_pass=false`)

| Field | Value |
|---|---|
| Instruction | "How many rows in orders.csv have a null (empty) customer_id? Answer with the number." (`tasks.py:123-126`) |
| Gold | `7`, computed at `tasks.py:116` |
| Probe output | `17`, built at `probes.py:52` (`f"1{gold}"`) |
| Naive verdict | score 1, runs `[1,1,1,1,1]`, error **FP**. Reason: "output contains gold answer '7'". Grader: `naive.py:19-22` (`if task["gold"] in output`). |
| Hardened verdict | score 0, runs `[0,0,0,0,0]`, `graded_by=judge`. Reason: "judge (mock): numeric mismatch: 17 != 7". |
| Hardened path | the exact check fails (`hardened.py:87`), so `MockJudge` is called (`hardened.py:89-92`). The numeric rule applies (`judge.py:39-48`). |

**Supplementary FP with a table diff: `T4_revenue_by_region × partial`**

| Field | Value |
|---|---|
| Naive verdict | FP. "header matches and row count is 4". Grader: `naive.py:25-32`. |
| Hardened verdict | correct fail. "a row differs (total_amount: expected '1537.27', got '1538.27')" |
| UI diff | `/api/case/T4_revenue_by_region/partial → diff.only_in_output = [["North-East","1538.27","12"]]` (`serve.py:76`, `hardened.py:155-171`). Captured on screen earlier in this session. |

**False negative: `A2_completed_revenue × paraphrase`** (`should_pass=true`)

| Field | Value |
|---|---|
| Instruction | total amount of completed orders, "Give two decimals" (`tasks.py:128-131`) |
| Gold | `9469.30` |
| Probe output | `Completed orders total $9,469.30.` (`probes.py:59`) |
| Naive verdict | score 0, error **FN**. Reason: "gold answer '9469.30' not found in output". |
| Hardened verdict | score 1 via judge. Reason: "judge (mock): numeric match: 9469.3 == 9469.3". |
| Why the variation is legitimate | The question asks for an amount. A currency sign and a thousands separator don't change the value, and the two decimals are present. |
| How the mock judge handles it | It strips commas (`judge.py:24-25`) and compares with a 0.005 tolerance (`judge.py:16, 45`). |

**Order is not always free.** `T5_top_customers × shuffled` is labeled `should_pass=false` because the task says "Row order matters". The naive grader passed it (FP). The hardened grader failed it: "row 1 differs (customer_id: expected 'C017', got 'C002'…)". The order check is at `hardened.py:144-145`.

## 7. Flakiness mechanism (checked, not assumed)

**What varies between repetitions.** Only `GradeContext.now`:

- `GradeContext.for_seed(seed)` sets `now = BASE_NOW + Random(seed).uniform(0, 600)` seconds (`audit/graders/__init__.py:11, 19-23`).
- Measured delays: seed 0 → 506.7 s, 1 → 80.6 s, 2 → 573.6 s, 3 → 142.8 s, 4 → 141.6 s.

**Who reads it.**

- Only `naive.grade_state`, and only when the task sets `naive_freshness_seconds` (S1 only: `tasks.py:236`; check at `naive.py:45-50`, window 300 s).
- Seeds 0 and 2 exceed 300 s, so they fail; seeds 1, 3 and 4 pass. That gives runs `[0, 1, 0, 1, 1]`.
- The hardened graders ignore `ctx`, and `MockJudge` is deterministic.

**Recorded detection.**

- `report.md § Flaky verdicts` and `results.json → summary.naive.flaky = 6` list exactly 6 cases, all `S1_finalize_run × naive`: gold, paraphrase, format_variant, substring_trap, shuffled, partial.
- S1 `look_done` is **not** flaky. Its `finished_at` is null, so the clock check is skipped (`naive.py:46`). S1 `noop` fails earlier, on status.
- Test: `tests/test_audit.py:36-39` asserts that the flaky set equals `{("S1_finalize_run", "naive")}`.

**Limitations to state in the video.**

- The "time-dependent" grader reads a **seeded, simulated clock**, so detection is guaranteed by construction. A real wall-clock bug is only caught if real time actually differs across runs. Nondeterminism from networks, rendering or async state is not modeled.
- With `k=1`, nothing can be flaky (`tests/test_integration_cli.py:42-48`).
- Majority voting hides flaky errors in the FP/FN counts (see §4).

## 8. One case traced end to end: `A1_null_customer_ids × substring_trap`

1. **Task.** `build_tasks()` (`audit/tasks.py:91`) computes `n_null` (`:116`) and creates task A1 with `gold = "7"` (`:122-126`).
2. **Probe.** `build_probes()` (`audit/probes.py:192`) → `answer_probe_set` (`:85`) → `_answer_probes` returns `("17", False)` (`:52`).
3. **On disk.**
   - `generate()` (`audit/generate.py:27`) writes `data/probes/A1_null_customer_ids/substring_trap.txt` (`:46`).
   - It appends the label `{"should_pass": false, …}` to `data/labels.json` (`:47`).
4. **Load.** `run_audit()` (`audit/runner.py:42`) loads tasks and cases (`:48-50`).
5. **Grade ×5.**
   - `_grade_k()` (`runner.py:27-39`) calls each grader with `GradeContext.for_seed(0..4)`.
   - naive: `naive.grade_answer` (`naive.py:19-22`) → 1 every run.
   - hardened: `hardened.grade_answer` (`hardened.py:86-94`) → exact check fails → `MockJudge.judge` (`judge.py:31-52`) → 0.
6. **Classify.** Majority = 1 with `should_pass=false` ⇒ `error = "FP"` (`runner.py:56-57`).
7. **Aggregate.** `_summarize` (`runner.py:90-101`) adds it to `naive.fp`. `_cell` (`runner.py:104-114`) adds it to `matrix.substring_trap.naive.fp`.
8. **Serialize.** `write_results()` (`runner.py:255-262`) writes `results.json`. `render_report()` lists the case under "Every wrong verdict" (`runner.py:207`).
9. **Serve.**
   - `GET /api/results` (`serve.py:55-58`) feeds the summary and matrix.
   - `GET /api/case/A1_null_customer_ids/substring_trap` (`serve.py:61-79`) adds the instruction, full output and gold.
10. **Display.**
    - On load, `main()` calls `selectCell("substring_trap", "naive")` (`static/index.html:195`).
    - The case list sorts wrong cases first, so A1 is first. `showCase` (`:258`, `:261+`) renders the verdict cards and the 5 run dots (`:270`).

## 9. Semantic judge boundary

**When the judge is called.** Only for `answer` tasks where the normalized exact match fails (`hardened.py:86-94`). Asserted by `tests/test_audit.py:42-51`.

**Mock judge rules** (`judge.py:28-52`):

- An empty answer fails.
- Any negation word ("not", "no", "isn't", "wrong", …) fails (`:14, 34-36`).
- Numeric tasks: exactly one distinct number, within 0.005 of gold (`:39-48`).
- Text tasks: every gold token must be present (`:49-52`).

**Recorded judge stats** (`results.json → judge`; `report.md § Semantic judge`):

- 26 judge calls inside hardened grading, all 26 agreeing with the label.
- Standalone mock judge on all 32 answer probes: 32/32.
- These are **mock** results, and they are partly circular: the mock rules were written alongside these probes.

**Real LLM judge.** `LLMJudge` (`judge.py:66-88`) calls LiteLLM only if `JUDGE_MODEL` is set and `litellm` is installed. It was **not run**: no key, `litellm` not installed. Tested only against a fake module (`tests/test_units.py:164-180`).

## 10. Tests (run at commit `c3dd9a2`, mock mode)

```
env -u JUDGE_MODEL python -m pytest -p no:asyncio -m unit -q          → 139 passed, 13 deselected
env -u JUDGE_MODEL python -m pytest -p no:asyncio -m integration -q   → 13 passed, 139 deselected
```

- `-p no:asyncio` disables an unrelated, user-installed `pytest-asyncio` plugin that prints a deprecation warning. The repo does not depend on it.
- **Mutation test.** `tests/test_audit.py:64-70` swaps the hardened answer check `==` for `in` (`monkeypatch.setattr(hardened, "_exact", lambda gold, out: gold in out)`). It asserts the audit reports hardened FP > 0, with `A1_null_customer_ids × substring_trap` among the caught cases.
- **Determinism tests.**
  - `tests/test_audit.py:80+`: the generator reproduces the committed `data/` byte for byte.
  - `tests/test_integration_cli.py:28-40`: the CLI pipeline reproduces the committed `results/`.

## 11. PRD vs implementation

| PRD item | Status | Note |
|---|---|---|
| 12 tasks (4/5/3), 96 probe outputs with labels | Implemented | |
| Graders return `{score, reason}` | Implemented | |
| 8 probes | Implemented | `shuffled` label depends on task |
| K=5 flakiness with a planted time-dependent grader | Implemented, with caveats | The clock is simulated from the seed; see §7 |
| Per-grader FP/FN/flaky rates | Implemented | Rates are aggregated over all tasks per grader kind. The per-task breakdown in `report.md` is counts only, not rates. |
| "probe × grader **confusion matrix**" | **Partially** | It's an error-count heatmap, not a confusion matrix |
| `report.md` lists every wrong verdict with task, probe, snippet, reason | Implemented | `runner.py:207-231` |
| Judge only for failed exact checks on `answer` tasks; mock = token overlap + numeric rule; judge log kept separately | Implemented | The mock also rejects negations, which goes beyond the PRD |
| Judge agreement for a real model if a key is present | **Not exercised** | Code path exists; never run with a real model |
| Unit tests: each hardened grader vs all 8 probes | Implemented | 96 parametrized cases |
| Mutation test | Implemented | one mutation (`==` → `in`) |
| UI: summary, matrix with click-through, case view with table diff, report + download | Implemented | |
| PRD example headline "Naive graders passed 3 of 12 no-op agents" | **Differs** | Measured: naive passed 1 of 12 no-op probes (T3 only). The headline is generated from the probe with the most FPs (`partial`, 8 of 12). |
| `make demo` generates, audits, serves at :8000 | Implemented | It also rewrites `results/`, deterministically |
| Dockerfile | Present, **not built or run** in this session | |
| LiteLLM behind a flag | Code present | `requirements-llm.txt` pins `litellm==1.55.0`; not installed or verified |

## 12. External claims (not verified in this session)

README/PRD cite:

- a HUD research post
- a Browserbase × HUD post
- OSWorld issues #518 and #487
- the OSWorld-V2 release notes

None of these were opened or verified in this session. Per the brief, the video should not state them as fact unless they are verified first. See the open question in `outline.md`.

## 13. Toolchain for later phases (checked, nothing installed yet)

| Tool | Status |
|---|---|
| Python 3.10–3.12 | Not on PATH. `uv 0.9.18` and `conda 25.1.1` are available and can provide 3.12 for `docs/kt-video/.venv`. |
| espeak-ng | **Not installed.** Kokoro/misaki uses it as a fallback for out-of-vocabulary words. Needs an install decision in Phase 4. |
| Node | v24.13.0 |
| ffmpeg | 9.0.1 |
| Playwright | Available via the Playwright MCP server. A Node `playwright` package for `render.mjs` would be installed under `docs/kt-video/`. |
