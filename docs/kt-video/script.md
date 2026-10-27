# Grader Audit KT video: script (Phase 2 checkpoint)

## How to read this file

**Approved decisions:**

- Open on the recorded A1 case; no external sources.
- Scene 4 shows a styled run-command card.
- Keep T4 briefly.
- Voice `af_heart` at speed 1.0.

**Sources:**

- Every number comes from the frozen snapshot `docs/kt-video/snapshot/results.json` (SHA-256 `de8c65a4…`), referred to below as **R**.
- `report.md` is the same run's Markdown report.
- Both were produced by:

```
env -u JUDGE_MODEL -u ANTHROPIC_API_KEY -u OPENAI_API_KEY python -m audit.runner --data <generated data> --out docs/kt-video/snapshot --k 5
```

Evidence and line references are in `evidence.md`.

**Conventions:**

- **Narration** is exactly what Kokoro will speak. It's written for the ear: numbers are spelled out where that helps, and file names are said as words.
- **On-screen text** is exactly what appears. Real code, identifiers and UI strings stay verbatim (`FP`, `_grade_k`, `9469.30`).
- **Visual beats** tie a narration phrase (in quotes) to what's on screen at that moment.
- **Color rule:** green means the verdict *agrees* with the label, red means it *disagrees*, amber means unstable or a caution. A wrong "PASSED" is red.

Four framing statements, as requested. Each is spoken at least once (scene in brackets):

1. Results apply only to these 96 synthetic cases [4, 10].
2. FP/FN counts use majority verdicts across five runs [4, 7].
3. Flakiness uses controlled, simulated-clock variation [7].
4. Judge results come from the mock judge and are not independent validation [6, 9].

---

## Scene 1: Can we trust the grader?

**Narration**

> Here is a synthetic task. How many rows in orders dot C S V have a null customer I D? The correct answer is seven. A scripted probe answers seventeen. The naive grader marks it correct, because the digit seven appears somewhere in the answer. Every score built on that grader inherits the error. So before trusting a benchmark score, it's worth testing the grader.

**On-screen text**

- Chapter label: `01 · Can we trust the grader?`
- Question card: `How many rows in orders.csv have a null (empty) customer_id? Answer with the number.`
- `Expected: 7`, then `Probe output: 17`
- Verdict card: `naive grader → PASSED` (red outline), with the reason `output contains gold answer '7'`
- Tag: `Label: should fail · Result: false positive`

**Visual beats**

| Phrase | Beat |
|---|---|
| "Here is a synthetic task" | Question card fades in |
| "The correct answer is seven" | `Expected: 7` appears |
| "answers seventeen" | `Probe output: 17` appears beside it. The "7" inside "17" is underlined in amber. |
| "marks it correct" | Verdict card slides in, outline red |
| "inherits the error" | Card dims; caption line `A wrong verdict becomes a wrong score.` |

**Sources**

- Instruction: `audit/tasks.py:123-126`
- Gold computed: `audit/tasks.py:116`
- Probe `f"1{gold}"`: `audit/probes.py:52`
- Naive substring check: `audit/graders/naive.py:19-22`
- Run artifact: R → `cases[task_id=A1_null_customer_ids, probe=substring_trap]`
  - `.output_snippet = "17"`
  - `.should_pass = false`
  - `.verdicts.naive = {score: 1, runs: [1,1,1,1,1], error: "FP", reason: "output contains gold answer '7'"}`

---

## Scene 2: What Grader Audit tests

**Narration**

> Grader Audit tests graders without running any model. It feeds them scripted probes: fixed outputs with a known label, should pass or should fail. A grader can be wrong in three ways. A false positive passes an output that should fail. A false negative fails an output that should pass. A flaky verdict changes between repeated runs of the same input. This is an independent prototype using synthetic tasks and scripted probes. It does not audit HUD's actual benchmarks.

**On-screen text**

- Chapter label: `02 · What it tests`
- `Scripted probe = fixed output + known label (should_pass)`
- Card 1 (red): `False positive (FP)` / `passed, but should_pass = false`
- Card 2 (red): `False negative (FN)` / `failed, but should_pass = true`
- Card 3 (amber): `Flaky` / `verdict differs across repeated runs`
- Footer, held for the disclosure: `Independent prototype · synthetic tasks · scripted probes · does not audit HUD's benchmarks`

**Visual beats**

| Phrase | Beat |
|---|---|
| "scripted probes" | A probe chip labeled `should_pass` enters a grader box |
| "A false positive" / "A false negative" / "A flaky verdict" | Each card appears on its phrase |
| "This is an independent prototype" | Footer fades in |

**Sources**

- Error classification: `audit/runner.py:56-57`
- Flaky definition: `audit/runner.py:35`
- Labels: `data/labels.json` (written at `audit/generate.py:47`)

---

## Scene 3: The synthetic test bench

**Narration**

> The bench has twelve synthetic data engineering tasks: four questions, five tables, and three pipeline run records to update. Each task gets eight probes, from the exact gold output to traps and partly wrong answers. Labels depend on the task. Shuffled rows are fine, except in a top five ranking, where order is the answer. That makes ninety-six cases. Forty-seven should pass, and forty-nine should fail.

**On-screen text**

- Chapter label: `03 · The test bench`
- Row labels: `A1–A4 answer`, `T1–T5 table`, `S1–S3 state`
- Column labels: `gold · paraphrase · format_variant · noop · substring_trap · look_done · shuffled · partial`
- Callout on `T5 × shuffled`: `order matters → should fail`
- Totals: `12 tasks × 8 probes = 96 cases` · `47 should pass` · `49 should fail`

**Visual beats**

| Phrase | Beat |
|---|---|
| "twelve synthetic data engineering tasks" | 12 row labels appear in three groups |
| "eight probes" | All eight column headers appear left to right |
| "Labels depend on the task" | Grid cells fill. Should-pass cells are outlined, should-fail cells are solid. |
| "except in a top five ranking" | The T5 × shuffled cell flips, with an amber callout |
| "ninety-six cases" | Totals line counts up |

**Sources**

- Tasks: `audit/tasks.py:123-260`
- Probe list: `audit/probes.py:11`
- Shuffled label depends on `order_matters`: `audit/probes.py:141`
- T5 `order_matters: True`: `audit/tasks.py:208-215`
- Run artifact: R → `meta.n_tasks = 12`, `meta.n_cases = 96`, `summary.naive.positives = 47`, `summary.naive.negatives = 49`

---

## Scene 4: Run the audit

**Narration**

> One command runs everything: Python, dash m, audit dot serve. It generates the data, runs both graders five times per case, and serves this page. The five runs are combined by majority vote into one verdict per case, and that verdict is what gets counted. The naive graders passed twenty of forty-nine should-fail cases, and failed fourteen of forty-seven should-pass cases. Six of ninety-six were flaky. The hardened graders made no errors, on these ninety-six synthetic cases only.

**On-screen text**

- Chapter label: `04 · Run the audit`
- Command card (monospace), verbatim from the recorded run:

```
$ python -m audit.serve
  naive     FP 20/49  FN 14/47  flaky 6/96
  hardened  FP 0/49  FN 0/47  flaky 0/96
  Grader Audit UI: http://localhost:8000
```

- Card caption: `mock judge · JUDGE_MODEL unset · k = 5 runs per grader per case`
- Real UI capture: the summary cards (they display `40.8%`, `29.8%`, `6.3%`, and `0.0%` ×3, with "20 of 49 should-fail" etc.)
- Small note beside the flaky metric: `6/96 cases; percentage rounding differs between views.`
- Overlay notes:
  - `FP/FN counted on the majority verdict of 5 runs`
  - `Scope: these 96 synthetic cases only`

**Visual beats**

| Phrase | Beat |
|---|---|
| "One command" | Command card types in. The output lines appear at once (static, from the recorded run). |
| "serves this page" | Crossfade to the real summary capture |
| "majority vote" | Five small dots collapse into one, with a note |
| "twenty of forty-nine" / "fourteen of forty-seven" / "Six of ninety-six" | Highlight box moves across the naive FP, FN and Flaky metrics |
| "no errors" | Highlight on the hardened card |
| "on these ninety-six synthetic cases only" | Scope note fades in under both cards |

**Sources**

- `prepare()` (generate → audit → write): `audit/serve.py:25-31`
- Console lines: `audit/serve.py:95-107`
- Majority vote: `audit/runner.py:30`
- Denominators: `audit/runner.py:91-100`
- Run artifact: R → `summary.naive = {fp: 20, negatives: 49, fn: 14, positives: 47, flaky: 6, total: 96}` and `summary.hardened = {fp: 0, fn: 0, flaky: 0}`. Same numbers in `report.md § Summary`.

**Display note:** the UI rounds 6/96 to `6.3%`, while `report.md` prints `6.2%` (Python rounds 6.25 to even). The narration uses counts, never percentages, so it matches both.

---

## Scene 5: A false positive, inspected

**Narration**

> The error-count heatmap shows wrong verdicts for each probe and grader. Click a cell to list its cases. Here's the substring trap on the naive grader. Case A1 shows the instruction, the probe's seventeen, and the gold seven. The label says should fail. The naive grader passed it, because the output contains seven. The hardened grader failed it: numeric mismatch. In table case T four, one regional total is off by a dollar. The naive check sees the right header and row count, and passes. The diff shows the changed row.

**On-screen text**

- Chapter label: `05 · A false positive`
- Real UI captures:
  - the probe × grader heatmap
  - the case list for `substring_trap × naive` (header: "7 of 12 verdicts wrong")
  - the A1 case view
  - the T4 case view
- Callouts quote the UI verbatim:
  - naive: `output contains gold answer '7'`
  - hardened: `judge (mock): numeric mismatch: 17 != 7`
  - T4 naive: `header matches and row count is 4`
  - T4 diff rows: `− output North-East 1538.27 12` / `+ gold North-East 1537.27 12`

**Visual beats**

| Phrase | Beat |
|---|---|
| "error-count heatmap" | Heatmap capture with a soft highlight over the naive column; label `error-count heatmap` |
| "Click a cell" | Highlight on the `substring_trap × naive` cell ("7 wrong"), then cut to the case list |
| "Case A1" | Cut to the A1 case view. Zoom to the instruction, then the output/gold panes. |
| "passed it" | Zoom on the naive verdict card (red outline, "false positive" tag) |
| "failed it" | Pan to the hardened card ("correct" tag) |
| "In table case T four" | Cut to the T4 partial case view |
| "the changed row" | Zoom on the diff table |

**Sources**

- Heatmap cell data: `audit/runner.py:104-114`
- Heatmap rendering: `static/index.html:215-237`
- Default cell on load: `static/index.html:195`
- Wrong-first sort: `static/index.html:239-258`
- Case endpoint: `audit/serve.py:61-79`
- Naive table check: `audit/graders/naive.py:25-32`
- Diff: `audit/graders/hardened.py:155-171`
- Run artifacts:
  - R → `matrix.substring_trap.naive = {wrong: 7, fp: 7}`
  - R → `cases[A1_null_customer_ids, substring_trap].verdicts.hardened.reason = "judge (mock): numeric mismatch: 17 != 7"`
  - R → `cases[T4_revenue_by_region, partial].verdicts.naive = {error: "FP", reason: "header matches and row count is 4"}`
  - `.verdicts.hardened.reason = "a row differs (total_amount: expected '1537.27', got '1538.27')"`
  - `GET /api/case/T4_revenue_by_region/partial → diff.only_in_output = [["North-East","1538.27","12"]]`
- "Off by a dollar": 1538.27 − 1537.27 = 1.00.

---

## Scene 6: A false negative, inspected

**Narration**

> Task A2 asks for the total of completed orders. The probe writes the gold amount with a dollar sign and a thousands comma. The value is unchanged, so it should pass. The naive substring check fails it. The hardened exact check fails too, so it asks the judge. In this run, that's the deterministic mock judge, not a model. It extracts one number and compares within half a cent. Order is different. In the top five table, the hardened grader correctly fails shuffled rows.

**On-screen text**

- Chapter label: `06 · A false negative`
- Real UI capture: the A2 paraphrase case view
- Callouts:
  - `Gold: 9469.30`
  - `Probe: Completed orders total $9,469.30.`
  - `Label: should pass`
  - naive: `gold answer '9469.30' not found in output` (red, "false negative")
  - hardened: `judge (mock): numeric match: 9469.3 == 9469.3` (green, "correct")
- Badge on the hardened card: `MOCK JUDGE · deterministic rules, not a model`
- After "Order is different": the real T5 shuffled case view, with the note `T5 × shuffled · label should fail (row order matters) · hardened verdict agrees with label`

**Visual beats**

| Phrase | Beat |
|---|---|
| "Task A2" | A2 case view with the instruction zoomed |
| "dollar sign and a thousands comma" | The `$` and `,` in the probe output are highlighted in cyan |
| "naive substring check fails it" | Zoom on the naive card (red) |
| "asks the judge" | Zoom on the hardened card; the `MOCK JUDGE` badge appears |
| "within half a cent" | Small rule card `one number · |value − gold| ≤ 0.005` |
| "Order is a different story" | T5 inset slides in |

**Sources**

- Instruction: `audit/tasks.py:128-131`
- Probe text: `audit/probes.py:59`
- Hardened exact-then-judge: `audit/graders/hardened.py:86-94`
- Mock rules: comma stripping `audit/graders/judge.py:24-25`; tolerance `judge.py:16, 45`; single-number rule `judge.py:42-43`
- Order check: `audit/graders/hardened.py:144-145`
- Run artifacts:
  - R → `cases[A2_completed_revenue, paraphrase]`: `should_pass = true`, `naive.error = "FN"`, `hardened.score = 1`, `hardened.graded_by = "judge"`, `hardened.judge.backend = "mock"`
  - R → `cases[T5_top_customers, shuffled]`: `should_pass = false`, `hardened.score = 0`

---

## Scene 7: Flakiness and repeatability

**Narration**

> Task S one has a planted naive check: the finish time must be under three hundred seconds old. Each of the five runs gets a simulated clock, set by its seed. Two of the five delays cross the limit, so the verdicts read: fail, pass, fail, pass, pass. The audit flags six flaky cases, all on this grader. Two caveats. The clock variation is controlled, so detection works by construction. And the majority vote hides some errors: this correct output failed two of five runs, but isn't counted as a false negative.

**On-screen text**

- Chapter label: `07 · Flakiness`
- Rule card: `naive S1 check: now − finished_at ≤ 300 s`
- Timeline axis `0 s … 600 s` with a threshold line at `300 s` (amber). Markers (green ✓ = run agrees with the should-pass label, red ✗ = disagrees):
  - `seed 0 · 506.7 s ✗`
  - `seed 1 · 80.6 s ✓`
  - `seed 2 · 573.6 s ✗`
  - `seed 3 · 142.8 s ✓`
  - `seed 4 · 141.6 s ✓`
- Real UI capture: the S1 gold case, naive card with the UI's run dots (fail, pass, fail, pass, pass); amber highlight on the dots
- Real capture of the report panel scrolled to `report.md § Flaky verdicts`: six rows, all `S1_finalize_run | naive | [0, 1, 0, 1, 1]`
- Caveat cards (amber):
  - `Simulated, seeded clock: detection is by construction`
  - `Majority vote: S1 gold failed 2/5 runs, not counted as FN`

**Visual beats**

| Phrase | Beat |
|---|---|
| "planted naive check" | Rule card |
| "simulated clock" | Timeline draws; label `GradeContext.for_seed(seed)` |
| "Two of the five delays" | Markers drop in one by one, with their measured delays on screen |
| "fail, pass, fail, pass, pass" | Markers recolor ✗/✓; cut to the real UI run dots |
| "six flaky cases" | Flaky table, with the six rows highlighted amber |
| "Two caveats" | Caveat cards appear on their phrases |

**Sources**

- Clock: `audit/graders/__init__.py:11, 19-23`
- Check: `audit/graders/naive.py:45-50`
- Window set only on S1: `audit/tasks.py:236`
- Flaky flag: `audit/runner.py:35`
- Majority: `audit/runner.py:30`
- Test: `tests/test_audit.py:36-39`
- Delays measured with:

```
python -c "from audit.graders import GradeContext, BASE_NOW; [print(s, (GradeContext.for_seed(s).now-BASE_NOW).total_seconds()) for s in range(5)]"
```

  Output: 506.7, 80.6, 573.6, 142.8, 141.6 (evidence §7).
- Run artifacts: R → `summary.naive.flaky = 6`; R → `cases[S1_finalize_run, gold].verdicts.naive = {runs: [0,1,0,1,1], score: 1, flaky: true, error: null}`; `report.md § Flaky verdicts`.

**Narration note:** the five measured delays are shown on screen only, not read aloud.

---

## Scene 8: How the code produces the report

**Narration**

> Here's how one case reaches the screen. Build tasks creates task A1 and its gold answer. Build probes creates the seventeen, labeled should fail. Generate writes both to disk. Run audit loads every case, and grade k calls each grader five times with a seeded context. The majority verdict is tagged a false positive, counted in the summary and heatmap, and written to results dot json and the report. FastAPI serves it to this page.

**On-screen text**

- Chapter label: `08 · How it runs`
- Diagram nodes (monospace), left to right:
  1. `tasks.build_tasks()`
  2. `probes.build_probes()`
  3. `generate.generate()` → `data/probes/…/substring_trap.txt` + `data/labels.json`
  4. `runner.run_audit()`
  5. `runner._grade_k()` ×5 → `naive.grade()` / `hardened.grade()`
  6. `error = "FP"`
  7. `_summarize()` / `_cell()`
  8. `write_results()` → `results.json`, `report.md`
  9. `GET /api/case/{task}/{probe}`
  10. `index.html · showCase()`
- Token label: `A1 × substring_trap · output "17" · should_pass: false`

**Visual beats**

| Phrase | Beat |
|---|---|
| "Build tasks" | Cyan token appears at node 1 |
| Each function name | Token moves to the next node |
| "five times" | Node 5 pulses five times |
| "false positive" | Token turns red |
| "this page" | The final node shows a thumbnail of the A1 case capture |

**Sources:** evidence §8, steps 1–10:

- `audit/tasks.py:91, 116, 122-126`
- `audit/probes.py:52, 85, 192`
- `audit/generate.py:27, 46-47`
- `audit/runner.py:27-39, 42-63, 56-57, 90-114, 255-262`
- `audit/serve.py:61-79`
- `static/index.html:261`

---

## Scene 9: Why the hardened checks differ

**Narration**

> The hardened graders parse each output by its declared type, with float tolerance, null markers, date formats, and row order only when the task requires it. State checks compare every field, not just a done flag. For answers, the exact check runs first, and the judge is called only when it fails. That happened twenty-six times here, all with the mock judge. A real model judge is supported, but wasn't run. And since the mock's rules were written alongside these probes, its agreement is not independent validation.

**On-screen text**

- Chapter label: `09 · Hardened checks`
- Code excerpt, verbatim from `audit/graders/hardened.py:86-94`. The final excerpt will be pasted from the file at build time, not retyped.

```python
def grade_answer(task: dict, output: str, ctx: GradeContext, judge=None) -> dict:
    if _exact(normalize_text(task["gold"]), normalize_text(output)):
        return verdict(True, "exact match after normalization", graded_by="exact")
    judge = judge or judge_mod.get_judge()
    result = judge.judge(task, output)
    return verdict(result["score"], f"judge ({judge.name}): {result['reason']}", graded_by="judge",
                   judge={"backend": judge.name, **result})
```

- Two-lane diagram:
  - Lane 1 (cyan): `deterministic: normalize → typed compare → invariants`
  - Lane 2 (amber): `judge: answer tasks only, after exact check fails · this run: mock`
- Stat: `judge calls in this run: 26 · backend: mock`
- Caveat (amber): `Mock agreement ≠ independent validation`

**Visual beats**

| Phrase | Beat |
|---|---|
| "parse each output by its declared type" | Lane 1 list items appear |
| "the exact check runs first" | Highlight the `if _exact(...)` line |
| "only when it fails" | Highlight the `judge.judge(...)` line; lane 2 lights up |
| "twenty-six times" | Stat appears |
| "not independent validation" | Caveat card |

**Sources**

- `audit/graders/hardened.py:86-94` (answer)
- `:97-152` (table)
- `:174-213` (state)
- `NULL_TOKENS` / `DATE_FORMATS`: `hardened.py:24-25`
- Judge selection: `audit/graders/judge.py:91-99`
- Run artifacts:
  - R → `judge.log` (length 26)
  - R → `meta.judge_backend = "mock"`
- Not shown in the video: R → `judge.evaluation.mock` = 32/32. It's omitted on purpose, so mock agreement isn't presented as validation.

---

## Scene 10: Evidence and limits

**Narration**

> The evidence. One hundred fifty-two tests pass: one hundred thirty-nine unit, thirteen integration. They include every hardened grader against all eight probes. A mutation test swaps an equality check for a substring check in the hardened answer grader, and the audit reports a false positive on the A1 trap. So the harness measures all three error types against known labels, and separates the two graders on these ninety-six synthetic cases. It doesn't show the hardened graders are correct in general. They were written knowing these probe types. Nor does it cover real environments, or a real model judge. Future work: human-reviewed, model-generated adversarial probes, and adapters for real environments.

**On-screen text**

- Chapter label: `10 · Evidence and limits`
- Test card:

```
pytest -m unit         → 139 passed
pytest -m integration  →  13 passed
```

- Mutation card:
  - `_exact: gold_norm == out_norm  →  gold in out`
  - `→ audit reports hardened FP on A1 × substring_trap`
- Three columns:
  - **Demonstrated** (green: agreement with recorded evidence):
    - FP / FN / flaky measured against known labels
    - naive vs hardened separated on 96 synthetic cases
  - **Not established** (amber):
    - general correctness of hardened graders
    - real browser or desktop state
    - a real model judge
  - **Future work** (cyan):
    - model-generated adversarial probes, human-reviewed
    - adapters for real-environment graders
- End card: `Independent prototype · synthetic data · not affiliated with HUD`

**Visual beats**

| Phrase | Beat |
|---|---|
| "One hundred fifty-two tests" | Test card |
| "mutation test" | Mutation card: `==` strikes through and becomes `in`, then a red FP badge |
| "So the harness measures" | Column 1 |
| "It doesn't show" | Column 2 |
| "Future work" | Column 3 |
| End | End card |

**Sources**

- Tests: `tests/test_hardened.py:18-21` (96 cases)
- Mutation: `tests/test_audit.py:64-70`
- Commands and results: evidence §10:
  - `env -u JUDGE_MODEL python -m pytest -p no:asyncio -m unit -q` → 139 passed
  - `… -m integration -q` → 13 passed
  - both at commit `c3dd9a2`
- Limits: README "Limitations and next steps"

**Note:** the mutation test runs `run_audit(k=1)` with the mock judge.

---

## Word count and timing (measured)

Measured from the Kokoro audio (`af_heart`, speed 1.0) in `timing.json`. Each scene is followed by 0.6 s of silence.

| Scene | Starts | Words | Speech |
|---|---|---|---|
| 1: Can we trust the grader? | 00:00.00 | 65 | 26.53 s |
| 2: What Grader Audit tests | 00:27.13 | 79 | 33.59 s |
| 3: The synthetic test bench | 01:01.31 | 66 | 29.15 s |
| 4: Run the audit | 01:31.06 | 78 | 33.90 s |
| 5: A false positive, inspected | 02:05.56 | 91 | 37.24 s |
| 6: A false negative, inspected | 02:43.41 | 84 | 33.99 s |
| 7: Flakiness and repeatability | 03:18.00 | 92 | 36.83 s |
| 8: How the code produces the report | 03:55.43 | 75 | 31.38 s |
| 9: Why the hardened checks differ | 04:27.41 | 87 | 34.33 s |
| 10: Evidence and limits | 05:02.33 | 109 | 48.16 s |
| **Total** | | **826** | **351.10 s (5:51.10) including padding** |

Trimmed during Phase 4 to fit the 5–6 minute target without speeding up the voice. The trims:

- **Scene 7:** the five delays are shown on screen, not read aloud.
- **Scene 3:** a shorter spoken probe list.
- **Scenes 1, 5, 6, 9, 10:** small redundancies removed.
- **Scene 5:** "not a confusion matrix" removed and replaced with "error-count heatmap".

"A one" and "A two" are written as `A1` and `A2`, because Kokoro read "A one" as the article "uh one".

## Spoken vs displayed

| Spoken | Displayed |
|---|---|
| "orders dot C S V", "customer I D" | `orders.csv`, `customer_id` |
| "Python, dash m, audit dot serve" | `python -m audit.serve` |
| "grade k", "build tasks", "build probes", "run audit" | `_grade_k`, `build_tasks()`, `build_probes()`, `run_audit()` |
| "results dot json", "labels dot json" | `results.json`, `labels.json` |
| "T four", "S one" (A1 and A2 are written as A1/A2 so Kokoro says the letter, not "uh") | `A1`, `A2`, `T4`, `S1` |
| "false positive" / "false negative" | `FP` / `FN` |
| The A2 amount is described, not read aloud | `9469.30` and `$9,469.30` stay on screen |
