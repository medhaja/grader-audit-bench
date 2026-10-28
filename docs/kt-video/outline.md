# Grader Audit KT video: outline

**Audience:** HUD founders and engineers seeing this code for the first time.
**Target:** about 3:45 across 8 scenes, roughly 520–540 spoken words at 145 wpm.
**Order:** the problem, then the architecture, then one case traced through the real functions, then the details that matter, then running it, then gotchas and a recap.

## What the system does

Grader Audit tests benchmark **graders**, not agents.

It builds a synthetic mini-benchmark of 12 data-engineering tasks (4 `answer`, 5 `table`, 3 `state`). For each task it writes 8 scripted "probe" outputs, so 96 cases in total, and each case carries a known `should_pass` label.

Every case goes through two graders:
- a **naive** grader, built from publicly reported failure patterns: substring match, header-plus-row-count, and trusting a `status` field;
- a **hardened** grader: typed normalization, real data equality, and a semantic judge for free-text answers only.

Each grader runs 5 times per case, each time with a seeded clock. The runner then counts:
- **false positives:** a pass on a should-fail case;
- **false negatives:** a fail on a should-pass case;
- **flaky verdicts:** the verdict changes across the 5 runs.

Results are written to `results/results.json` and `results/report.md`, and FastAPI serves them to a one-page UI.

It's for benchmark engineers who want to show that a grader is fair before any model runs against it. It's an independent prototype on synthetic data and is not affiliated with HUD.

**Colors on screen.** Each color has one meaning throughout:

| Color | Meaning |
|---|---|
| Blue | data and probe outputs moving through the system |
| Amber | stored state on disk (`data/`, `results/`) |
| Violet | a grader or judge |
| Green | the verdict agrees with the label |
| Red | a wrong verdict (FP or FN) |

---

## Scenes

### 1. The grader can be the bug (~25 s)

- **Idea:** If a grader passes a wrong answer, the benchmark score inherits the error.
- **Visual:**
  - A task card: "How many rows in orders.csv have a null customer_id?", with gold `7`.
  - A probe card answering `17` slides in. A naive grader box stamps PASS with the reason `output contains gold answer '7'`, outlined red.
  - A small source strip cites the public reports listed in PRD.md: OSWorld issue #518 (substring match) and #487 (flaky checks).
- **Files:** `PRD.md:7-14`, `audit/tasks.py:122-126`, `audit/probes.py:50`, `audit/graders/naive.py:19-22`

### 2. The idea: grade the grader (~25 s)

- **Idea:** You can audit a grader without running a model. Feed it outputs whose correct verdict you already know.
- **Visual:**
  - A 12 × 8 grid (tasks × probes) fills in cell by cell. Green-outlined cells are should-pass; grey-outlined cells are should-fail.
  - The `T5 × shuffled` cell flips, because row order matters for the top-5 task.
  - Three definition chips follow: FP (pass on should-fail, out of 49), FN (fail on should-pass, out of 47), flaky (verdict changes across runs, out of 96).
- **Files:** `audit/probes.py:11-22`, `audit/probes.py:141`, `audit/runner.py:56-57`, `audit/runner.py:90-101`

### 3. Architecture (~30 s)

- **Idea:** A straight pipeline: generate, then grade, then measure, then serve. Everything is deterministic from one seed.
- **Visual:** Boxes appear left to right, and arrows animate in the order data moves:
  1. `tasks.py` (seeded generator, `SEED = 1337`)
  2. `probes.py` (8 probes and their labels)
  3. `generate.py`, which writes `data/` (amber)
  4. `runner.py`, which calls `graders/naive.py`, `graders/hardened.py` and `graders/judge.py` (violet)
  5. `results/results.json` and `report.md` (amber)
  6. `serve.py` (FastAPI)
  7. `static/index.html`
- **Files:** `audit/tasks.py:16`, `audit/generate.py:27-50`, `audit/runner.py:42-87`, `audit/serve.py:25-31`, `PRD.md:62`

### 4. One case, end to end (~45 s)

- **Idea:** Trace `A1_null_customer_ids × substring_trap` through the real functions.
- **Visual:** A blue token labelled `"17"` travels through a column of function names, lighting each one as the narration reaches it:
  1. `load_cases()`
  2. `run_audit()`
  3. `_grade_k(k=5)` with `GradeContext.for_seed(0..4)`
  4. The path splits:
     - **Naive branch:** `naive.grade_answer`, `gold in output`, score 1.
     - **Hardened branch:** `normalize_text`, `_exact` (fails), `MockJudge.judge`, `numeric mismatch: 17 != 7`, score 0.
  5. Back in `run_audit`, the error classifier marks naive FP (red) and hardened correct (green).
- **Files:** `audit/generate.py:64-70`, `audit/runner.py:50-58`, `audit/runner.py:27-39`, `audit/graders/__init__.py:19-23`, `audit/graders/naive.py:19-22`, `audit/graders/hardened.py:86-92`, `audit/graders/judge.py:37-47`
- **Recorded values:** `results/results.json` case A1 × substring_trap: naive runs `[1,1,1,1,1]` FP; hardened `[0,0,0,0,0]`, `graded_by: judge`.

### 5. Naive vs hardened, in code (~30 s)

- **Idea:** The hardened graders compare typed data, never surface signals.
- **Visual:** Code focus, split screen.
  - **Left:** `naive.py` `grade_table`. Header plus row count, 8 lines.
  - **Right:** `hardened.py` `grade_table`. Normalize, row count, key uniqueness, then sorted row equality (unless order matters), about 12 lines.
  - Lines highlight as the narration names each check.
  - A one-line callout follows: `normalize_cell` turns `1.50`, `1.5` and `1.5000001` into the same value. It rejects `MM/DD` dates as ambiguous.
- **Files:** `audit/graders/naive.py:25-32`, `audit/graders/hardened.py:126-152`, `audit/graders/hardened.py:24-25`, `audit/graders/hardened.py:63-81`

### 6. Flakiness from a seeded clock (~25 s)

- **Idea:** Repeat runs catch time-dependent graders. The clock is simulated, so the flakiness can be reproduced.
- **Visual:**
  - A timeline with `BASE_NOW 10:15:00` and five seed ticks at their offsets (seeds 0–4, each between 0 and 600 s later).
  - A 300 s freshness window is shaded.
  - The S1 gold case's five run dots fill in as `0 1 0 1 1`: majority PASS, flagged flaky (amber ring).
  - Caption: "flaky = verdicts differ across seeds; only S1 × naive is flagged."
- **Files:** `audit/graders/__init__.py:9-23`, `audit/graders/naive.py:45-51`, `audit/tasks.py:235-236`, `audit/runner.py:27-39`, `tests/test_audit.py:36-39`
- **Recorded values:** S1 × gold, naive runs `[0,1,0,1,1]`.

### 7. Run it, and what it found (~30 s)

- **Idea:** One command regenerates, audits and serves. Here are the numbers on these 96 synthetic cases.
- **Visual:**
  - A terminal card with `python -m audit.serve` and the printed summary lines.
  - The real UI summary capture (synthetic data), then the matrix capture.
  - A results table:

    | Grader | FP | FN | Flaky |
    |---|---|---|---|
    | naive | 20 / 49 | 14 / 47 | 6 / 96 |
    | hardened | 0 | 0 | 0 |

  - A footer chip: "152 tests, including a mutation test that swaps `==` for `in`."
- **Files:** `audit/serve.py:95-109`, `audit/serve.py:25-31`, `results/report.md:11-14`, `tests/test_audit.py:64-70`, `README.md:190`

### 8. Gotchas, limits, next steps, recap (~35 s)

- **Idea:** What the numbers do and don't prove.
- **Visual:** A "with / without" list, then a recap of 5 one-liners.
- **Gotchas found in the code:**
  - The hardened graders' 0 / 0 is **by construction**: they were written knowing these 8 probes (`README.md:152-154`).
  - The naive state check uses `target not in status`, so `"not_succeeded"` slips through as a substring (`audit/graders/naive.py:42`). Verified: all three S tasks × `substring_trap` are naive FPs in `results/results.json` (reason `status 'not_succeeded' looks complete`).
  - Flakiness is simulated, and real flakiness would need real repeated runs (`audit/graders/__init__.py:9-10`).
  - The LLM judge is optional. On any error it falls back to the mock for that call. The audit doesn't fail; the fallback only shows up in the reason text (`audit/graders/judge.py:86-88`). The real-model path was not run.
  - `serve` rewrites `data/` on every start (`audit/generate.py:29-30`, `audit/serve.py:27`). It's safe because generation is byte-identical (`tests/test_audit.py:80-92`).
- **Limits and next steps** (from `README.md:213-220`): labels are assumed known; synthetic CSV and JSON rather than browser or desktop state. Next: LLM-generated adversarial probes with human review, environment adapters, and an audit of a public benchmark's real graders.
- **Recap:** probes with known labels, then naive vs hardened, then FP, FN and flaky over K=5 seeded runs, then one command, then honest limits.

---

## Open questions

1. **Old video in `docs/kt-video/`.** A previous 5:51 demo-style video, with its sources and assets, is already committed here. I've overwritten `outline.md` (the old one is in git at `ac26995`).
   - My plan is to replace that pipeline in place. I'd keep the fonts and reuse `assets/ui/summary.png` and `matrix.png` (they still match the current `results.json` byte for byte).
   - I'd delete the files the new video doesn't use: `capture.mjs`, `evidence.*`, `qa.md`, `snapshot/`, the other screenshots and the old composition.
   - I'd also update the Makefile `kt-video` target and drop `kt-video-capture`. OK, or do you want the old video kept alongside?
2. **External sources on screen.** Scene 1 names OSWorld issues #518 and #487 and HUD's "What is a good task?" post. These come from PRD.md, not the code, so their source reference will be `PRD.md:9-11`. Is it OK to name them on screen and in the narration?
3. **Voice.** I plan neutral third person ("this prototype…") rather than first person. OK?
4. **Real UI screenshots** in scene 7, or a clean redrawn schematic? I recommend the real screenshots, since they show synthetic data only.
5. **Personal details.** PRD.md includes personal and employer details (Bizmetric, visa and location). I'll leave all of these out. Tell me if you want the Bizmetric "deterministic first, LLM only where it adds signal" framing in scene 3.
