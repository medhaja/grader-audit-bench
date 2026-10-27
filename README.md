# Grader Audit

```bash
pip install -r requirements.txt && python -m audit.serve     # or: make install && make demo
# → open http://localhost:8000
```

Independent prototype built from public information and synthetic data. Not affiliated with HUD.

## What it is

A small harness that runs scripted **probe agents** against benchmark **graders** and measures how often
each grader gives the wrong verdict. Every probe output has a known true label, so the audit can count
false positives (a wrong output scored 1), false negatives (a correct output scored 0) and flakiness (the
verdict changes between runs). It ships a synthetic mini-benchmark of 12 data-engineering tasks, with two
graders per task: a `naive` one built from publicly reported failure patterns and a `hardened` one. The
results go to `results/results.json`, `results/report.md` and a one-page web UI.

## The problem it targets (outside-in)

From the outside, the hardest part of a credible agent benchmark looks like the grader, not the agent.

- HUD's post [What is a good task?](https://www.hud.ai/research/what-is-a-good-task) says benchmarks lose
  trust mostly because of the task itself. Examples include graders that score the wrong thing (a correct
  answer scored 0% because it was worded differently) and tasks that leave reward-hacking paths open.
- The [Browserbase × HUD post](https://www.browserbase.com/blog/browserbase-hud-frontier-evals) warns that
  agents can edit pages to fool graders that only check whether a task *looks* done.
- On [OSWorld's issue tracker](https://github.com/xlang-ai/OSWorld/issues), #518 reports reward=1 from loose
  substring matching and #487 reports flaky scores from non-deterministic checks. The
  [OSWorld 2.0 release](https://github.com/xlang-ai/OSWorld-V2/releases) changed 14 tasks to stop reward hacking.
- [HUD](https://www.hud.ai) already offers QA agents that audit traces for false positives, false negatives
  and reward hacking.

This repo explores a repeatable way to show a grader is fair *before* any model runs against it.

## What the demo shows

| Screen | What you see |
|---|---|
| **Summary** | Naive vs hardened side by side: FP %, FN %, flaky %, plus a one-line headline. |
| **Matrix** | A probe × grader heatmap of wrong verdicts. Clicking a cell lists the 12 cases behind it, wrong ones first. |
| **Case** | Task instruction, probe output vs gold output, both graders' verdicts and reasons, the 5 per-seed runs, and a normalized row diff for table tasks. |
| **Report** | The rendered `report.md` with a download button. It lists every wrong verdict with task, probe, output snippet and grader reason. |

Current results on the synthetic data (K=5 runs per grader, majority verdict):

| Grader | False positives | False negatives | Flaky |
|---|---|---|---|
| naive | 20/49 (40.8%) | 14/47 (29.8%) | 6/96 (6.2%) |
| hardened | 0/49 (0.0%) | 0/47 (0.0%) | 0/96 (0.0%) |

The hardened graders scoring 0/0 is **by construction**: they were written knowing these 8 probe types.
The numbers show the harness catches the failure modes; they don't show the hardened graders are robust
to failure modes nobody has thought of yet (see Limitations).

**2-minute demo script**

1. Run the command at the top and open the page. Read the two summary cards: the naive graders pass 4 in 10 wrong outputs and fail 3 in 10 correct ones.
2. The matrix opens on `substring_trap × naive`. Click `A1_null_customer_ids`: the gold answer is `7`, the probe answered `17`, and the substring grader passed it.
3. Click `partial × naive`, then `T4_revenue_by_region`. The header + row-count check passed a table with a wrong total. The diff shows the one changed row.
4. Click `look_done × naive`, then an `S*` task. A run record that just says `"status": "done"` passed.
5. Click `paraphrase × naive`, then `A2_completed_revenue`. `$9,469.30` is correct but failed the substring check. The hardened grader sent it to the judge, which accepted it.
6. Click `gold × naive`, then `S1_finalize_run`. The five run dots disagree: this is the planted clock-dependent grader, and it is the only one flagged as flaky.
7. Scroll to Report and download `report.md`.

## How it works

```
audit/tasks.py     seeded generator: 12 tasks (4 answer, 5 table, 3 state) with gold outputs
audit/probes.py    8 scripted probes per task, each with a should_pass label
audit/generate.py  writes data/ (committed, byte-for-byte deterministic)
audit/graders/     naive.py, hardened.py, judge.py
audit/runner.py    K=5 seeded runs per grader → FP/FN/flaky, probe×grader matrix → results/
audit/serve.py     FastAPI + static/index.html (vanilla JS, no build step)
```

- **Tasks.** The 4 `answer` tasks ask questions like "how many rows have a null customer_id?". The 5 `table` tasks cover dedupe, join, type-cast, aggregate and top-N. The 3 `state` tasks have the agent update a pipeline-run JSON record. Built-in edge cases: nulls vs `NULL`/empty strings, floats that need a tolerance, duplicate keys, Unicode names (including NFC vs NFD), a gold answer (`7`) that is a substring of a wrong one (`17`), ambiguous `MM/DD/YYYY` dates, and one table (`T5`) where row order matters.
- **Probes.** `gold`, `paraphrase`, `format_variant`, `noop`, `substring_trap`, `look_done`, `shuffled` and `partial`. Labels are per task: `shuffled` should pass everywhere except `T5`.
- **Naive graders** copy real failure patterns. Answers use substring matching. Tables use a header + row-count check, the usual "copy succeeded" validation in ETL pipelines. State tasks trust the `status` field. On `S1`, the naive grader also checks that `finished_at` is "recent" against the clock. The clock is simulated from each run's seed, so this flakiness can be reproduced.
- **Hardened graders** parse and normalize by declared type: Unicode NFC, null tokens, float tolerance, accepted date formats, case-insensitive headers. They then check invariants (row count, key uniqueness) and compare real data. They never trust a `done` flag.
- **Semantic judge.** It is only called for `answer` tasks where the normalized exact check fails. The default `MockJudge` is deterministic: normalized token overlap, a numeric-equivalence rule (single number within 0.005), and rejection of negated or hedged answers. To use a real model, `pip install -r requirements-llm.txt` and set `JUDGE_MODEL` plus the provider key (see `.env.example`); calls go through LiteLLM. Judge verdicts are logged separately and checked against the labels in the report. No API key is needed for anything else.
- **Mutation test.** `tests/test_audit.py` injects a bug into the hardened answer grader (swaps `==` for `in`). It confirms the audit catches it as a false positive on `A1 × substring_trap`.

Other commands: `make generate`, `make audit` (CLI summary + `results/`), `make test`, and
`docker build -t grader-audit . && docker run -p 8000:8000 grader-audit`.

## Tests

```bash
python -m pytest -q                  # all 152 tests (~7 s)
python -m pytest -q -m unit          # 139 unit tests (or: make test-unit)
python -m pytest -q -m integration   # 13 integration tests (or: make test-integration)
```

**Unit tests** (`tests/test_units.py`, `tests/test_hardened.py`) cover:

- every hardened grader against all 8 probes (96 parametrized cases)
- the type normalizers: floats, nulls, dates, UTC timestamps, Unicode NFC
- each naive grader's known blind spot
- the seeded clock
- the mock judge's rules
- the optional LLM judge, against a fake `litellm` module (reply parsing and the fallback when the call fails), with no network

**Integration tests** (`tests/test_audit.py`, `tests/test_integration_cli.py`, `tests/test_api.py`) cover:

- the full generate → audit → report pipeline
- the expected naive failure modes
- the flakiness check flagging only the planted grader
- the mutation test (`==` swapped for `in`)
- the real CLI commands run in subprocesses, which must reproduce the committed `results/` byte-for-byte
- every HTTP endpoint the UI uses

## Limitations and next steps

- **Hand-written probes only find the failures I thought of.** The hardened graders pass every probe because both were written by the same person. Next step: LLM-generated adversarial probes, reviewed by a human before they become labeled cases.
- **Synthetic tasks are cleaner than real ones.** Real graders often check browser or desktop state, not CSVs and JSON. The probe ideas carry over (look-done, substring, no-op), but the harness would need adapters for those environments.
- **Ground-truth labels are assumed known.** In practice, labeling is the expensive part, and I don't know how HUD labels ground truth for its QA agents today.
- **The flakiness is simulated.** The time-dependent grader reads a seeded clock so the demo is reproducible. Real flakiness (network, rendering, async state) would need real repeated runs.
- **The real LLM judge path is optional and was not exercised here.** The demo and tests use the mock. Running it with a key would report the LLM judge's agreement next to the mock's.
- Natural follow-up: point the same harness at a public benchmark's real graders and publish the audit as a write-up.

Not production software. Nothing here uses or reflects HUD's internal systems, data or users.

## License

MIT, see [LICENSE](LICENSE).
