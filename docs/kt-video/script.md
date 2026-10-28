# Grader Audit KT video: script

## How this file is used

`tts.py` reads this file:
- Each scene starts with a `## NN ·` heading.
- Narration is the `> ` lines under **Narration**.
- Everything else is notes for the visuals and for review.

**Narration** is written as it should be spoken. Acronyms are hyphenated so Kokoro reads them letter by letter: A-P-I, L-L-M, C-S-V, O-S World. Captions map these back to normal spelling through `CAPTION_SUBS` in `tts.py`.

**On screen** beats are keyed to spoken phrases. The composition looks up each phrase in Kokoro's word timestamps.

**Colors.** Each color has one meaning in every scene:

| Color | Meaning |
|---|---|
| Blue | data and probe outputs in motion |
| Amber | stored state on disk |
| Violet | a grader or judge |
| Green | the verdict agrees with the label |
| Red | a wrong verdict |
| Dashed red | flaky (unstable) |

**Recorded values** come from `results/results.json` (mock judge, K = 5, seeds 0–4), extracted by `facts.py` into `facts.json`.

---

## 01 · The grader can be the bug

Chapter label: `01 / The problem`

### Narration

> Here's a benchmark task. How many orders have a null customer ID? The answer is seven. A scripted agent answers seventeen, and the naive grader passes it, because seven appears inside seventeen. Public reports, like O-S World issue five eighteen, describe exactly this. When the grader is wrong, the score measures the grader, not the agent.

### On screen

- **At start:** a task card appears: "How many rows in orders.csv have a null (empty) customer_id?" with a gold chip `7`.
- **At "answers seventeen":** a blue probe card `17` slides in from the left.
- **At "passes it":**
  - A violet box `naive.grade_answer` stamps PASS.
  - The reason `output contains gold answer '7'` types in.
  - The card is outlined red because the label is "should fail".
- **At "appears inside":** the `7` inside `17` underlines.
- **At "Public reports":** a small source strip appears with "OSWorld #518: reward = 1 from loose substring matching (cited in PRD.md)".
- **At "measures the grader":** the PASS row dims, and the line "A wrong grader corrupts the score." appears at the bottom.

### Sources

- The task asks for the count of null `customer_id` rows; gold is 7 → `audit/tasks.py:124-125`, `data/tasks/A1_null_customer_ids/gold.txt`
- The probe answers "17" → `audit/probes.py:46-50`, `data/probes/A1_null_customer_ids/substring_trap.txt`
- The naive grader passes by substring → `audit/graders/naive.py:19-21`
- Recorded: naive score 1, error FP, reason "output contains gold answer '7'" → `results/results.json` (A1 × substring_trap)
- OSWorld issue #518 → `PRD.md:11` (external, cited from the PRD and not re-verified here)

---

## 02 · Grade the grader

Chapter label: `02 / The idea`

### Narration

> This prototype grades the grader, without running a model. Twelve synthetic data-engineering tasks each get eight scripted probe outputs. Gold, paraphrase, no-op, substring trap, a fake that only looks done, and more. All ninety-six cases have a known label. A false positive passes a case that should fail. A false negative fails one that should pass. A flaky verdict changes between runs.

### On screen

- **At "grades the grader":** the title "Audit the grader, not the agent" appears.
- **At "Twelve synthetic":** 12 row labels drop in (`A1–A4`, `T1–T5`, `S1–S3`), tinted by type: answer, table, state.
- **At "eight scripted":** 8 probe column headers appear, each lighting as it's named.
- **At "ninety-six cases":**
  - The grid fills: should-pass cells get green outlines, should-fail cells grey.
  - The counter reads 96 = 47 should-pass + 49 should-fail.
  - `T5 × shuffled` reads `fail*`, with a footnote: "T5 is a top-5 table where row order matters, so shuffled rows should fail there."
- **At "A false positive":** three cards slide up, one per sentence:
  - False positive (red): "score 1 on a should-fail case", out of 49
  - False negative (red): "score 0 on a should-pass case", out of 47
  - Flaky (dashed red): "verdict differs across the 5 runs", out of 96

### Sources

- No model is run → `PRD.md:27`, `audit/probes.py:1`
- 12 tasks (4 answer, 5 table, 3 state) → `audit/tasks.py:121-266`
- 8 probes → `audit/probes.py:11-22`
- 96 labeled cases → `audit/generate.py:44-47`, `results/report.md:5`
- 47 / 49 → `results/report.md:13`
- Shuffled is should-fail only where order matters (T5) → `audit/probes.py:141`, `audit/tasks.py:209-213`
- FP and FN → `audit/runner.py:56-57`
- Flaky → `audit/runner.py:35`

---

## 03 · Architecture

Chapter label: `03 / Architecture`

### Narration

> It's a straight pipeline. Tasks dot py generates twelve tasks from one fixed seed. Probes dot py adds eight labeled outputs per task, and generate dot py writes them to the data folder. Runner dot py grades every case five times per grader, then writes results and a report. Serve dot py, a Fast A-P-I app, serves them to one static page.

### On screen

The boxes build left to right and wrap to a second row. Arrows draw in the direction data flows.

- **At "Tasks dot py":** the box `audit/tasks.py` appears, with `build_tasks()` and `SEED = 1337`.
- **At "Probes dot py":** the box `audit/probes.py` appears with `build_probes()`, and a blue arrow draws to it.
- **At "generate dot py":** the box `audit/generate.py` appears, then an amber cylinder `data/` with `tasks/`, `probes/` and `labels.json`.
- **At "Runner dot py":**
  - The box `audit/runner.py` appears with `run_audit()`, and a blue arrow draws from `data/`.
  - Three violet sub-boxes fan out: `naive.py`, `hardened.py` and `judge.py` (dashed, "optional LLM").
- **At "writes results":** an amber cylinder `results/` appears with `results.json` and `report.md`.
- **At "Serve dot py":** the box `audit/serve.py` appears with `/api/results`, `/api/case/…` and `/api/report`, then the box `static/index.html`.

### Sources

- One fixed seed → `audit/tasks.py:16`, `audit/tasks.py:91-93`
- Labeled probe outputs → `audit/probes.py:192-200`
- generate writes `data/` → `audit/generate.py:27-50`
- 5 runs per grader per case → `audit/runner.py:27-28`, `audit/runner.py:42`, `audit/runner.py:50-55`
- Writes `results.json` and `report.md` → `audit/runner.py:255-262`
- FastAPI endpoints and the static page → `audit/serve.py:21`, `audit/serve.py:50-92`
- The judge is an optional LLM, with the mock as fallback → `audit/graders/judge.py:91-99`

---

## 04 · One case, end to end

Chapter label: `04 / Tracing one case`

### Narration

> Let's follow that seventeen through the code. Run audit loads each labeled case, and calls grade K for every grader. Grade K runs it five times, with seeds zero to four, and takes the majority vote. The naive grader asks one question: is the gold string in the output? It is, so it scores one. The hardened grader normalizes both strings and needs an exact match. That fails, so it asks the judge. That's a deterministic mock by default, and it returns numeric mismatch, seventeen versus seven. Score zero. Finally, a pass on a should-fail case is recorded as a false positive.

### On screen

A vertical trace. The blue token `"17"` moves down a column of real function names, and each name lights as the token arrives.

- **At "Run audit loads":** a node `runner.run_audit()` appears with a small `generate.load_cases()` feeding in (`labels.json → {task_id, probe, should_pass, output}`).
- **At "grade K":** the node `runner._grade_k(…, k=5)` appears.
- **At "seeds zero to four":** five seed pips `0 1 2 3 4` appear, followed by "→ majority vote".
- **At "naive grader asks":** the trace splits. The left column (violet) shows `naive.grade_answer` and `if task["gold"] in output:`.
- **At "scores one":** five red-outlined dots fill `1 1 1 1 1`.
- **At "hardened grader":** the right column (violet) shows `hardened.grade_answer` and `_exact(normalize_text(gold), normalize_text(output))`.
- **At "That fails":** a ✗ appears beside `_exact`.
- **At "deterministic mock":** a node `judge.MockJudge.judge` appears, and the chip `numeric mismatch: 17 != 7` types out.
- **At "Score zero":** five green-outlined dots fill `0 0 0 0 0`.
- **At "Finally":**
  - The columns merge into `v["error"] = "FP" if v["score"] and not case["should_pass"] …`.
  - The naive side gets a red `FP` badge; the hardened side gets a green ✓.

### Sources

- `load_cases` reads `labels.json` and attaches outputs → `audit/generate.py:64-70`; called at `audit/runner.py:50`
- `run_audit` calls `_grade_k` per grader → `audit/runner.py:50-55`
- K runs over seeds 0..k-1, then the majority vote → `audit/runner.py:27-31`; `GradeContext.for_seed` → `audit/graders/__init__.py:19-23`
- Naive substring check → `audit/graders/naive.py:19-22`
- Hardened: normalize, exact match, then the judge → `audit/graders/hardened.py:34-41`, `audit/graders/hardened.py:86-92`
- The mock is the default and is deterministic, with a numeric rule → `audit/graders/judge.py:91-99`, `audit/graders/judge.py:1-6`, `audit/graders/judge.py:37-47`
- Recorded: hardened "judge (mock): numeric mismatch: 17 != 7", runs `[0,0,0,0,0]`; naive runs `[1,1,1,1,1]`, FP → `results/results.json`
- Error classification → `audit/runner.py:56-57`

---

## 05 · Naive vs hardened, in code

Chapter label: `05 / The graders`

### Narration

> Tables show the same contrast. The naive grader checks the header and the row count, so a table with one wrong total still passes. The hardened grader normalizes each cell by its declared type. So one point five zero equals one point five, and month-first dates are rejected as ambiguous. Then it checks the row count, unique keys, and every row.

### On screen

A code-focus scene in two steps. The real excerpts are read from source by `facts.py`, each with its file path above the pane. Only one highlight group is active at a time.

**Step 1: `audit/graders/naive.py` lines 25–32** (all 8 lines, full width).
- **At "header":** line 28 highlights.
- **At "row count":** line 30 highlights.
- **At "one wrong total":** a red chip appears under the pane: `T4_revenue_by_region × partial`, `North-East · total_amount 1538.27 (gold 1537.27)`, `naive PASS`, and the reason "header matches and row count is 4".

**Step 2: `audit/graders/hardened.py`.** 12 lines (126–129, 134, 139–142, 144–147) plus 3 `…` gap markers, 15 rows in all.
- **At "hardened grader normalizes":** the naive pane collapses into a one-line bar, "naive.py:25-32 header + row count → passed a table with one wrong total", and the hardened pane slides in.
- **At "each cell":** lines 128–129 highlight.
- **At "one point five":** a callout shows `hardened.py:69 · normalize_cell`: `1.50 · 1.5 · 1.5000001 → "1.5"`.
- **At "month-first":** a callout shows `hardened.py:25`: `DATE_FORMATS = ["%Y-%m-%d", "%Y/%m/%d"]`, with "MM/DD/YYYY rejected: ambiguous".
- **At "checks the row count":** line 134 highlights.
- **At "unique keys":** lines 139–142 highlight.
- **At "every row":** lines 144–147 highlight.

### Sources

- Naive table check → `audit/graders/naive.py:25-32`
- Recorded T4 × partial: naive "header matches and row count is 4" (FP); hardened "a row differs (total_amount: expected '1537.27', got '1538.27')" → `results/results.json`
- Normalize by declared type → `audit/graders/hardened.py:97-119`, `audit/graders/hardened.py:63-81`
- 1.50 equals 1.5 → `audit/graders/hardened.py:69`
- Month-first dates are rejected → `audit/graders/hardened.py:25`; tested at `tests/test_hardened.py:32-36`
- Row count, keys, rows → `audit/graders/hardened.py:132-150`

---

## 06 · Flakiness from a seeded clock

Chapter label: `06 / Flakiness`

### Narration

> Why five runs? Some graders depend on time. Task S-one plants one. Its naive grader fails a run when "finished at" is more than three hundred seconds old. The clock is simulated from the seed, up to ten minutes after a fixed time. So the correct answer passes three runs and fails two. The majority says pass, but it's flagged flaky. It's the only grader flagged.

### On screen

- **At "Why five runs":** five empty run circles appear: "naive runs, seeds 0–4".
- **At "S-one":** a JSON card shows S1's gold `status`, `finished_at` (`2025-06-01T10:15:00Z`) and `rows_written`, with a violet tag "naive grader · freshness window 300 s".
- **At "simulated from the seed":**
  - A timeline runs from `BASE_NOW 10:15:00 = finished_at` to `+600 s`, with the 0–300 s band shaded "fresh".
  - Five ticks drop on at each seed's real offset (computed by `facts.py` from `GradeContext.for_seed`): green inside the band, red outside.
- **At "passes three runs":** the run circles fill `0 1 0 1 1`.
- **At "majority says pass":** chips appear: "majority: PASS" (green) and "flaky: runs disagree" (dashed red).
- **At "only grader flagged":** a footer reads `tests/test_audit.py:36-39  flaky == {("S1_finalize_run", "naive")}`.

### Sources

- Planted on S1 with a 300 s window → `audit/tasks.py:235-236`, `audit/graders/naive.py:45-51`
- Seeded clock: `BASE_NOW` plus uniform(0, 600) s → `audit/graders/__init__.py:9-23`
- S1 gold `finished_at` is 10:15:00Z → `audit/tasks.py:226`
- Recorded: S1 × gold naive runs `[0,1,0,1,1]`, score 1, flaky → `results/results.json`
- Majority and the flaky flag → `audit/runner.py:30-35`
- Only S1 × naive is flaky → `tests/test_audit.py:36-39`

---

## 07 · Run it, and what it found

Chapter label: `07 / Running the demo`

### Narration

> To run it, install the requirements, then python dash m audit dot serve. That regenerates the data, runs the audit, and serves the page on port eight thousand. No A-P-I key is needed. On these ninety-six synthetic cases, the naive graders pass twenty of forty-nine wrong outputs, and fail fourteen of forty-seven correct ones. The hardened graders make zero errors. A hundred and fifty-two tests pass, including a mutation test.

### On screen

- **At "To run it":** a terminal card appears with `pip install -r requirements.txt` and `python -m audit.serve`.
- **At "serves the page":** the printed output appears line by line, formatted as `serve.py:105-108` prints it: the two summary lines, the headline, then the UI URL.

  ```
  naive     FP 20/49  FN 14/47  flaky 6/96
  hardened  FP 0/49  FN 0/47  flaky 0/96
  Naive graders passed 8 of 12 partial agents and wrongly failed 14 of 47 correct outputs; …
  Grader Audit UI: http://localhost:8000
  ```

- **Shortly after "serves the page":** the real UI capture `summary.png` (synthetic data) appears on the right.
- **At "No A-P-I key":** a card appears: "No API key · mock judge by default · JUDGE_MODEL=<model> opts in".
- **At "naive graders pass twenty":** a red highlight appears on the naive FP figure.
- **At "fourteen":** the highlight moves to the naive FN figure.
- **At "zero errors":** the highlight moves to the hardened card (green).
- **About 1 s later:** `matrix.png` appears below.
- **At "hundred and fifty-two":** a card reads "152 tests pass · mutation test: hardened `_exact` swapped from == to in → audit catches it as a false positive · tests/test_audit.py:64-70".

### Sources

- The command → `README.md:4`
- `serve` regenerates, audits and serves; default port 8000 → `audit/serve.py:25-31`, `audit/serve.py:98`, `audit/serve.py:104-109`
- No key needed; `JUDGE_MODEL` opts into the LLM → `audit/graders/judge.py:91-99`, `.env.example:1-3`
- 20/49, 14/47, hardened 0 → `results/report.md:11-14`
- 152 tests → `README.md:190`; confirmed locally (152 passed)
- Mutation test → `tests/test_audit.py:64-70`

---

## 08 · Limits, next steps, recap

Chapter label: `08 / Limits & recap`

### Narration

> Now, the caveats. The hardened graders score zero by construction, because they were written knowing these probes. One gotcha: the naive state grader checks status by substring, so "not succeeded" passes. The flakiness is simulated, and the real L-L-M judge was never run. Labels are assumed known, and the tasks are synthetic files, not browser state. Next: adversarial probes from an L-L-M, reviewed by a human. To recap: known labels, two graders, five seeded runs, one command.

### On screen

- **Gotcha cards** stack one at a time, each with a mono source tag:
  - **At "by construction":** "0 / 0 is by construction" `README.md:152`.
  - **At "One gotcha":** a code card with `naive.py:42`, `if target not in status and status not in DONE_WORDS:`, and below it `"not_succeeded" ⊃ "succeeded"` with a red PASS.
  - **At "simulated":** "seeded clock, not real time" `graders/__init__.py:9`.
  - **At "never run":** "LLM judge path not exercised; it falls back to the mock on error" `judge.py:86`.
  - **At "Labels are assumed":** "labels assumed known · synthetic CSV and JSON".
- **At "Next":** the cards slide left, and a blue item appears: "adversarial probes: LLM-generated, human-reviewed".
- **At "To recap":** the screen clears to four lines, each appearing on its keyword:
  - Known labels → audit the grader
  - Two graders, the same 96 cases
  - Five seeded runs → FP · FN · flaky
  - `python -m audit.serve`
- **Final padding:** the footer reads "Independent prototype built from public information and synthetic data. Not affiliated with HUD."

### Sources

- Zero by construction → `README.md:152-154`
- Naive state substring check → `audit/graders/naive.py:40-43`. Recorded: S1, S2 and S3 × substring_trap are naive FPs, with reasons like "status 'not_succeeded' looks complete" → `results/results.json`
- Simulated flakiness → `audit/graders/__init__.py:9-10`, `README.md:218`
- LLM judge not exercised → `README.md:219`; fallback → `audit/graders/judge.py:86-88`
- Labels assumed; synthetic, not browser state → `README.md:216-217`
- Next step → `README.md:215`
- Disclaimer → `README.md:8`
