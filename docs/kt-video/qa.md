# QA: Grader Audit KT video

**Final output:** `out/grader-audit-demo.mp4`, 16.0 MB, **5:51.10**. Built from commit `c3dd9a2`, with application code unchanged.

## 1. Durations and encoding (measured with ffprobe)

| Check | Result |
|---|---|
| Video stream | H.264, 1920×1080, 30 fps, `yuv420p`, TV range, BT.709, CRF 20; 10,533 frames |
| Audio stream | AAC, 48 kHz, ~157 kbps (target 160k) |
| Video vs audio duration | 351.100 s vs 351.100 s, **difference 0.000 s** (limit 0.2 s) |
| `timing.json` total | 351.100 s: 10 scenes plus 10 × 0.6 s padding |
| `+faststart` | `moov` atom precedes `mdat` |
| Loudness | Two-pass EBU R128 normalization: narration measured -25.7 LUFS, output **-16.1 LUFS**, true peak -1.4 dBFS |

**Two fixes during QA:**

- The first render came out `yuvj420p` because the frame pipe carries full-range JPEG frames. Fixed with an explicit full→TV range conversion to `yuv420p`.
- The narration was quiet (-25.7 LUFS), so loudness normalization was added before muxing. Level only; timing is unchanged.

## 2. Frames inspected

**Composition stills** (`node render.mjs --qa`, `out/stills/`):

- 29 stills: the mid point, late point and start boundary of every scene.
- Every scene was reviewed, including both code-focus scenes: 8 (call path) and 9 (verbatim `hardened.py:86-92`).

**Frames decoded from the final MP4** (`out/verify/`):

- The mid frame of every scene: `sheet_mids.png`.
- A scene 4→5 transition at −0.20, −0.05, +0.10 and +0.30 s: `sheet_transition.png`.

**Fixed after inspection:**

- **Ligatures:** JetBrains Mono turned `!=`/`==` into ≠ and a long equals, so real grader reasons were not shown verbatim. Ligatures are now disabled.
- **Clipping:** a highlight was clipped at the frame edge (scene 4), and a token label overflowed the right edge (scene 8).
- **Overlaps:**
  - Scene 7: timeline labels collided, and the S1 zoom showed a cut-off line of text.
  - Scene 8: node numbers overlapped long function names.
  - Scene 6: the T5 note was truncated and overlapped the footer.
- **Rendering artifact:** a dark rectangle came from a `box-shadow` on a highlight in mid-fade.
- **Hover outline:** the first capture had the sticky nav over the heatmap and a hover outline on a case row. Recaptured.
- **Transitions:** crossfades stacked two dense layouts. They now fade through the background.

**Accepted as is:** scene 3 shows the empty 12 × 8 grid headers for about 6 s (70.4–76.5 s) before the labels fill in on "Labels depend on the task". This is intentional pacing.

## 3. Transitions, blank frames and determinism

- **Blank frames:** every frame (30 fps) was scanned for total scene opacity. Each transition goes through the background on purpose; the longest stretch below 50% opacity is **0.20 s**, and none exceeds 0.25 s.
- **Determinism:** the same time, rendered before and after a different time, gives byte-identical PNGs.
- **No live inputs:** there are no CSS transitions or animations, no randomness, no wall-clock reads and no network. Fonts and images are inlined as data URIs.

## 4. Text size, contrast, clipping, sensitive data

| Check | Result |
|---|---|
| Text size | Smallest text in the composition is 17–18 px mono (grid cells, timeline labels) at 1080p. Body copy is 22–40 px. |
| UI captures | 2× device-scale captures; they are zoomed wherever their small UI text carries the point. |
| Colors | Green is used only for agreement with the expected verdict, red for disagreement, and amber for instability or caution. A naive "PASSED" on a should-fail case is red. |
| Sensitive data | The composition contains no user paths, emails, keys or env values; the scan found 0 matches. |
| Mock mode | The captured app ran with `JUDGE_MODEL` unset, and `capture.mjs` verified `meta.judge_backend == "mock"`. |
| Synthetic data | Only synthetic data is shown. `evidence.md` and `script.md` mention API-key environment variable *names* only, in the commands that unset them. |

## 5. Numbers checked against the recorded artifacts

These were checked automatically against `snapshot/results.json` (SHA-256 `de8c65a4…`), and all passed:

- **Summary:** naive FP 20/49, FN 14/47, flaky 6/96; hardened 0/49, 0/47, 0/96.
- **Totals:** 47 should-pass, 49 should-fail, 96 cases, 12 tasks.
- **Judge:** 26 calls, backend mock.
- **A1 × substring_trap:** output `17`, naive FP, hardened fail.
- **A2 × paraphrase:** naive FN; hardened pass via the mock judge.
- **S1 × gold:** naive runs `[0,1,0,1,1]`, flaky, not counted as FN.
- **Flaky cases:** only on S1 naive.
- **T4 partial:** 1538.27 vs 1537.27.
- **Spoken numbers:** "twenty of forty-nine", "fourteen of forty-seven", "Six of ninety-six", "twenty-six" match the same fields.

**On-screen numbers come from data or from real captures:**

- Summary cards, terminal card, grid and judge count are generated from the snapshot data inside the composition.
- UI images are real captures. `capture.mjs` refused to run unless the live `/api/results` deep-equalled the snapshot.
- `render.mjs` refuses to build if the capture manifest's snapshot hash differs.

**Values not in the snapshot** (`evidence.json`) were re-verified on 2026-10-28:

- `pytest -m unit` → 139 passed; `pytest -m integration` → 13 passed.
- `GradeContext.for_seed(0..4)` delays → 506.7, 80.6, 573.6, 142.8, 141.6 s.
- `hardened.py:86-92` still starts with `def grade_answer(`. The build checks this and copies the lines verbatim.

**Real UI values that differ by view:**

- The UI shows the naive flaky rate as `6.3%`; `report.md` prints `6.2%` (6/96 = 6.25%, rounded differently).
- Scene 4 labels this on screen: "6/96 cases; percentage rounding differs between views."
- The UI headline string says "partial agents". It's shown as captured; the narration says "scripted probes".

## 6. Narration claims vs implementation

Each claim in `script.md` carries a file:line reference. Rechecked after the Phase 4 trims:

- **Scope:** "on these ninety-six synthetic cases only" (scene 4) and "these ninety-six synthetic cases" (scene 10).
- **Majority vote:** `runner.py:30`, scene 4. The hidden S1 false negative is shown in scene 7.
- **Simulated clock:** `graders/__init__.py:19-23` and `naive.py:45-50`. "Controlled, so detection works by construction" is spoken in scene 7.
- **Mock judge:** "the deterministic mock judge, not a model" (scene 6). "All with the mock judge… real model judge… wasn't run… not independent validation" (scene 9).
- **Heatmap:** called an "error-count heatmap". The phrase "not a confusion matrix" was removed, as requested.
- **Order:** "hardened grader correctly fails shuffled rows" (T5) matches `hardened.py:144-145` and the snapshot.
- **Mutation test:** matches `tests/test_audit.py:64-70` (`_exact` swapped to `gold in out`; asserts A1 × substring_trap is caught).

## 7. Captions

- `out/captions.srt` is generated from the same `timing.json` as the audio: 91 cues.
- No overlaps or negative durations; at most 2 lines of 42 characters.
- The last cue ends at 350.5 s, before the final padding.
- **Exact:** sentence start and end times come from the measured audio.
- **Estimated:** where a sentence is split into several cues, the split points are proportional to character count. They are not word-aligned.
- **Display forms:** captions show what the screen shows: `orders.csv`, `python -m audit.serve`, `_grade_k`, `A1`, numerals.
- **Orphan cues:** an early version produced a 0.4 s "answer." fragment. Cues are now balanced.

## 8. Audio and pronunciation

- **Listening was not performed.** No audio playback was available in this environment, and transcript review is not an audio check.
- **What was checked instead:**
  - Integrated loudness, true peak and silence detection: no clipping.
  - The longest silence is 1.5 s, at a scene boundary. Inter-sentence pauses are about 0.8 s.
  - Kokoro's phonemes for risky words were inspected.
- **Found and fixed:** "A one" / "A two" were read as the article ("uh one"). The narration now writes `A1` / `A2`, which phonemize as the letter A. Only the affected sentences were re-synthesized.
- **Checked and judged acceptable:**
  - "FastAPI" → fast-A-P-I.
  - "dot json" → "jay-son".
  - "grade k" → "grade kay".
  - "orders dot C S V", "customer I D".
  - "HUD's" → "huds", read as a word. HUD's preferred pronunciation was not verified.

## 9. Remaining limitations

1. **Nobody has listened to the audio yet.** Please listen once before sharing, especially for "HUD's", "FastAPI" and pacing.
2. **Word timestamps:** visual beats use Kokoro's own word timestamps, which come from its predicted durations, not forced alignment. Caption splits within a sentence are estimates (§7).
3. **Recapture server:** the UI recapture ran against a mock-mode server process left over from an earlier start. The new server couldn't bind the port. This was harmless, because the capture verified the results against the snapshot before taking any screenshot. The process was then identified and stopped.
4. **Platform:** rendered on Windows with Chromium 1200 (Playwright 1.57.0). Other platforms may anti-alias text slightly differently, but the timing and content are the same.
5. **Downloads:** first-time setup downloads the Kokoro-82M weights and spaCy's `en_core_web_sm`. All inference is local.
6. **The audit was not rerun for the video.** It uses the Phase 1 snapshot, byte-identical to the committed `results/`.
