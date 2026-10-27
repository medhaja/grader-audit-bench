# Grader Audit KT video: outline (Phase 1 checkpoint)

**Target:** about 5:45, ten scenes, roughly 760–820 spoken words.
**Sources:** all numbers come from `snapshot/results.json` (SHA `de8c65a4…`), and all code references are listed in `evidence.md`.
**Order:** problem (1–2) → working demo (3–7) → implementation (8–9) → evidence and limits (10).

---

### 1. Can we trust the grader? (~25 s)

| | |
|---|---|
| **Takeaway** | A grader can pass a wrong answer, and the benchmark score inherits the error. |
| **Narration** | A synthetic task asks how many orders have a null customer ID, and the correct answer is 7. A scripted probe answers 17. The naive grader marks it correct. It simply checks whether "7" appears somewhere in the answer. If graders do this at scale, the scores measure the grader, not the agent. |
| **Visual** | A plain question card. Expected "7" next to the probe's "17". A naive verdict card reading "PASSED", outlined red because it disagrees with the expected verdict. |
| **Evidence** | `snapshot/results.json → cases[A1_null_customer_ids, substring_trap].verdicts.naive` (score 1, error FP); `naive.py:19-22`; `probes.py:52` |
| **Open** | Whether to add an external motivation line (see open question Q1). The default is no external citation. |

### 2. What Grader Audit tests (~30 s)

| | |
|---|---|
| **Takeaway** | You can test a grader without running any model: feed it outputs whose correct verdict you already know. |
| **Narration** | Explain scripted probes: fixed outputs, each with a label `should_pass`. Then the three error types. A false positive is a pass on an output labeled should-fail. A false negative is a fail on an output labeled should-pass. A flaky verdict is one that changes across repeated runs of the same input. Include the independent-prototype disclosure here. |
| **Visual** | Three definition cards. Red for FP and FN (they disagree with the label), amber for flaky. Each card states its denominator. |
| **Evidence** | `runner.py:56-57` (error classification), `runner.py:91-100` (denominators) |
| **Open** | None |

### 3. The synthetic test bench (~25 s)

| | |
|---|---|
| **Takeaway** | 12 tasks × 8 probes = 96 labeled cases, all synthetic. |
| **Narration** | There are 4 answer tasks, 5 table tasks and 3 pipeline-state tasks, all in data engineering. Then name the 8 probes. Labels depend on the task: shuffled rows are fine everywhere except the top-5 table, where order is part of the answer. That gives 47 should-pass and 49 should-fail cases. |
| **Visual** | A 12 × 8 grid that fills in. Columns are colored by label, and T5 × shuffled flips. Counts are shown: 47 / 49. |
| **Evidence** | `tasks.py:123-260`, `probes.py:11, 141`; `summary.naive.positives = 47`, `negatives = 49` |
| **Open** | None |

### 4. Run the audit (~35 s)

| | |
|---|---|
| **Takeaway** | One command; naive vs hardened side by side. |
| **Narration** | `python -m audit.serve` generates the data, runs every grader 5 times per case, and serves the page. Naive: 20 of 49 false positives, 14 of 47 false negatives, 6 of 96 flaky. Hardened: 0, 0 and 0, **on these 96 synthetic cases**. Five runs are combined by majority vote into one verdict per case. |
| **Visual** | A short terminal card showing the command, plus the printed summary lines from the recorded run. Then the real UI summary cards (captured screenshot), with highlight boxes on each metric. |
| **Evidence** | `serve.py:25-31, 95-109`; `summary.*`; `report.md § Summary` |
| **Open** | None |

### 5. A false positive, inspected (~45 s)

| | |
|---|---|
| **Takeaway** | The case view shows why a grader was wrong, not just that it was. |
| **Narration** | Click the substring-trap × naive cell in the heatmap (call it an "error heatmap", not a confusion matrix). Open A1. Walk through the instruction, the probe output "17", gold "7", and the label should-fail. The naive grader reasons "output contains gold answer '7'". The hardened grader's mock judge says "numeric mismatch: 17 != 7". Then one table example, T4 partial. The naive header-and-row-count check passes it. The hardened grader's diff shows the one changed row: North-East, 1538.27 against 1537.27. |
| **Visual** | Real captures: the heatmap with the cell highlighted, the case list, the A1 case view with verdict cards, then the T4 case view zoomed on the diff table. |
| **Evidence** | `cases[A1…, substring_trap]`, `cases[T4…, partial]`; `/api/case/T4_revenue_by_region/partial → diff`; `static/index.html:195, 239-258` |
| **Open** | Q3 (keep T4 or drop it to save about 12 s) |

### 6. A false negative, inspected (~35 s)

| | |
|---|---|
| **Takeaway** | Strict string checks fail correct answers too. |
| **Narration** | A2 asks for the total of completed orders, to two decimals. The gold answer is 9469.30, and the probe writes "Completed orders total $9,469.30." The value is the same: a currency sign and a thousands separator don't change an amount. Naive: "not found in output", a false negative. The hardened exact check also fails, so it hands the answer to the **mock** judge, which extracts one number and compares it within half a cent. Contrast with T5, where shuffled rows are correctly *failed*, because that task defines order as part of the answer. |
| **Visual** | Real capture of the A2 paraphrase case. Small inset of the T5 label to show that order is not always free. |
| **Evidence** | `cases[A2…, paraphrase]`; `probes.py:59`; `judge.py:16, 24-25, 39-48`; `cases[T5…, shuffled]` |
| **Open** | None |

### 7. Flakiness and repeatability (~40 s)

| | |
|---|---|
| **Takeaway** | Repeating each grading run exposes a grader that depends on time, and only that grader. |
| **Narration** | S1 has a planted naive check: finished_at must be under 300 seconds old. The "clock" is simulated from each run's seed, with delays of 507, 81, 574, 143 and 142 seconds. Runs 1 and 3 fail and the rest pass, giving 0-1-0-1-1. The audit flags 6 flaky cases, all on S1's naive grader. Then two caveats. First, the clock is simulated, so detection works by construction; real nondeterminism needs real repeated runs. Second, a majority vote hides some errors: S1 gold failed 2 of 5 runs but isn't counted as a false negative. |
| **Visual** | Real capture of the S1 gold case with the 5 run dots. A timeline animation with five delay markers against a 300 s threshold line (amber). The flaky table from `report.md`. |
| **Evidence** | `graders/__init__.py:11, 19-23`; `naive.py:45-50`; `tasks.py:236`; measured delays (evidence §7); `report.md § Flaky verdicts`; `tests/test_audit.py:36-39` |
| **Open** | None |

### 8. How the code produces the report (~40 s)

| | |
|---|---|
| **Takeaway** | One case moves through six real functions to reach the screen. |
| **Narration** | Follow the A1 case token through the path: `build_tasks` → `build_probes` → `generate` writes `data/` and `labels.json` → `run_audit` → `_grade_k` runs each grader five times → majority vote and FP/FN tag → `_summarize` / `_cell` → `write_results` → FastAPI `/api/case` → the page. |
| **Visual** | Architecture diagram from the verified call chain, with a cyan token moving node to node. File:function labels in monospace. |
| **Evidence** | Evidence §8, steps 1–10 |
| **Open** | None |

### 9. Why the hardened checks differ (~30 s)

| | |
|---|---|
| **Takeaway** | Deterministic, typed checks first; a semantic judge only where wording varies. |
| **Narration** | The hardened graders parse each output by type: Unicode, nulls, float tolerance, date formats, row order only when the task says so. They never trust a "done" flag. For answer tasks, the exact check runs first, and the judge is called only when it fails. That happened 26 times in this run, all 26 with the **mock** judge. A real model judge is supported but was not run here. |
| **Visual** | Real code excerpt `hardened.py:86-94` (`grade_answer`, 9 lines). Then a two-lane diagram: "deterministic" (cyan) vs "judge: mock" (amber label "mock, not a model"). |
| **Evidence** | `hardened.py:86-94`; `judge.py:28-52, 91-99`; `results.json → judge.log` (26/26) |
| **Open** | None |

### 10. Evidence and limits (~40 s)

| | |
|---|---|
| **Takeaway** | What this run shows, and what it doesn't. |
| **Narration** | **Tests:** 152 passing, 139 unit and 13 integration. That includes all 96 hardened cases and a mutation test that swaps `==` for `in` in the hardened answer grader; the audit then reports a false positive on A1 substring trap. **Demonstrated:** the harness measures FP, FN and flakiness against known labels, and separates the two graders on this synthetic set. **Not established:** that the hardened graders are correct in general. They were written knowing these 8 probe types. Also not established: the synthetic tasks reflect real browser or desktop state, or the real-model judge. **Future work:** model-generated adversarial probes reviewed by a human, and adapters for real environment graders. |
| **Visual** | Three-column card: Demonstrated (green ticks for agreement) / Not established (amber) / Next (cyan). Test counts with the commands. |
| **Evidence** | `pytest -m unit` → 139 passed; `pytest -m integration` → 13 passed; `tests/test_audit.py:64-70`; README "Limitations" |
| **Open** | None |

---

## Material PRD vs implementation differences

Full table in `evidence.md §11`.

1. **"Confusion matrix" is an error-count heatmap.** The video will call it a probe-by-grader error heatmap.
2. **The flaky grader reads a seeded, simulated clock**, not wall-clock time. Detection of the planted grader is real in the recorded run, but it is guaranteed by construction.
3. **Majority vote over 5 runs.**
   - FP/FN are counted per case, after aggregation.
   - Two of the naive grader's 20 FPs (S1 substring_trap and S1 partial) exist only because 3 of 5 seeded runs passed.
   - Flaky failures on correct outputs (e.g. S1 gold, 2 of 5 runs failed) are not counted as FN.
4. **The real LLM judge was never run.** All judge numbers are mock-judge numbers, and the mock was written alongside these probes.
5. **The PRD example headline ("3 of 12 no-op agents") doesn't match the data.** The naive graders passed 1 of 12 no-op probes. The generated headline picks `partial` (8 of 12) and says "agents"; the narration will say "scripted probes".
6. **Per-task results are counts, not rates.** The Dockerfile was not built.

## Open questions for you

- **Q1. External motivation.** README/PRD cite a HUD post, a Browserbase × HUD post, and OSWorld issues #518/#487, none of which I verified. I recommend opening with the recorded A1 case only and citing nothing external. The alternative is to let me fetch and verify one source in Phase 2 and quote it narrowly.
- **Q2. Showing commands.** Scene 4 shows the run command and recorded output as a styled card rather than live terminal footage. OK?
- **Q3. T4 table diff in Scene 5.** Keep it (it shows the diff feature) or drop it to bring the runtime nearer 5:30?
- **Q4. Phase 4 toolchain.**
  - Python 3.12 for `docs/kt-video/.venv` would come from `uv`, which downloads a managed CPython. espeak-ng isn't installed.
  - Options: (a) `winget install eSpeak-NG.eSpeak-NG`, or (b) try Kokoro without it and check pronunciation.
  - Approve one, or I'll ask again at Phase 4.
- **Q5. Voice and pace.** `af_heart` at speed 1.0 unless you prefer otherwise.
