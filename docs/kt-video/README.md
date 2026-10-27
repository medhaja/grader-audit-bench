# Grader Audit: narrated KT video

A 5:51 narrated walkthrough of this repository: the problem, the running app, how the audit works, the evidence, and the limits.

- **Narration:** generated locally with Kokoro.
- **Visuals:** rendered from a deterministic HTML composition.
- **Data:** every number comes from one frozen mock-judge audit run.

Nothing here changes the application.

| Output (ignored by git, rebuildable) | |
|---|---|
| `out/grader-audit-demo.mp4` | 1920×1080, 30 fps, H.264 CRF 20, yuv420p, AAC 160 kbps, +faststart |
| `out/captions.srt` | captions on the final audio timeline |
| `out/chapters.txt` | chapter start times |

## What's in this folder

| File | Role |
|---|---|
| `evidence.md` | Phase 1 record: commit, commands, counts, metric definitions, the traced case, PRD vs implementation |
| `outline.md`, `script.md` | Approved outline and script. **`script.md` is the narration source**: `tts.py` reads the `> ` lines. |
| `snapshot/results.json`, `snapshot/report.md` | Frozen audit results (mock judge, k = 5). Byte-identical to `results/` at commit `c3dd9a2`. |
| `evidence.json` | Recorded values not present in the snapshot: test counts, simulated-clock delays, code excerpt location |
| `assets/ui/*.png`, `assets/ui/manifest.json` | Real UI captures, plus element rectangles used for zooms and highlights |
| `assets/fonts/` | Inter and JetBrains Mono (OFL), inlined at build time |
| `capture.mjs` | Captures the running app. Refuses to capture if `/api/results` differs from the snapshot. |
| `tts.py` | Local Kokoro voiceover → `audio/`, `timing.json`, `out/captions.srt`, `out/chapters.txt` |
| `timing.json` | Scene, sentence and word timestamps for the final audio. Tracked so the visuals can be rebuilt. |
| `composition.src.html` | The composition. `window.renderAt(seconds)` is a pure function of time. |
| `render.mjs` | Inlines data and assets → `out/composition.html`, then renders the MP4 (or `--qa`, `--preview`) |
| `qa.md` | Verification results and remaining limitations |

## Setup (once)

```bash
cd docs/kt-video
npm install                                   # playwright 1.57.0 (uses Chromium build 1200), fonts
npx playwright install chromium               # only if that Chromium build isn't installed yet
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-tts.txt   # .venv/bin/python on macOS/Linux
```

**ffmpeg** must be on `PATH`.

**espeak-ng does not need a system install.** Kokoro's G2P falls back to the espeak-ng library bundled in `espeakng-loader`. If you prefer a system copy on Windows, it's `winget install eSpeak-NG.eSpeak-NG`.

**First run downloads** the Kokoro-82M weights (Hugging Face) and spaCy's `en_core_web_sm`. All synthesis runs locally.

## Rebuild the video

From the repo root:

```bash
make kt-video            # = cd docs/kt-video && .venv/Scripts/python tts.py && node render.mjs
```

Pass `KT_PY=.venv/bin/python` on macOS/Linux.

- **Audio cache:** sentence audio is cached in `audio/cache/` by text + voice + speed + library versions, so only edited sentences are re-synthesized.
- **Render time:** about 12–20 minutes on a laptop, piping JPEG frames straight into ffmpeg.

**The video never reruns the audit.** To change the numbers you must do it deliberately:

1. Run the audit in mock mode.
2. Replace `snapshot/`.
3. Recapture the UI (below).
4. Update `evidence.md` and `evidence.json`.

`render.mjs` aborts if the captures were taken against a different snapshot than the one in `snapshot/`.

## Edit

- **Narration:** edit the `> ` lines in `script.md`, then `make kt-video`.
  - Visual beats are tied to spoken phrases through Kokoro word timestamps (`at(scene, "phrase")` in `composition.src.html`).
  - If an edit removes a phrase that a beat uses, the build stops with `beat phrase not found`.
- **Visuals:** edit `composition.src.html`.
  - `node render.mjs --preview` builds `out/composition.html`; open it with `#preview` for play/scrub controls synced to `audio/narration.wav`.
  - `node render.mjs --qa` writes stills for every scene, scene boundaries and late-scene frames to `out/stills/`, and checks two things: determinism, and that no transition stays dark longer than 0.25 s.
- **UI captures:** start the app in mock mode, then capture:

  ```bash
  env -u JUDGE_MODEL python -m audit.serve
  make kt-video-capture
  ```

## Honesty constraints baked into the video

- Results are stated only for these 96 synthetic cases.
- FP and FN counts are majority verdicts over 5 runs.
- Flakiness comes from a seeded, simulated clock.
- All judge results are mock-judge results; mock agreement is not presented as validation.
- The real LLM judge was not run.
- Independent prototype; not affiliated with HUD.
