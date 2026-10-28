# Grader Audit: narrated KT walkthrough

A 3:59 narrated walkthrough of this repository, covering:

- the problem;
- the architecture;
- one case traced through the real functions;
- the graders side by side;
- flakiness;
- how to run it;
- the limits.

How it's made:

- **Voice:** Kokoro (`af_heart`), run locally.
- **Visuals:** a deterministic HTML composition, rendered frame by frame with Playwright Chromium.
- **Content:** every number and code excerpt is read from the repo at build time. Nothing on screen is typed by hand.

Nothing here changes the application.

## Outputs

| File | What it is |
|---|---|
| `kt-video.mp4` (committed) | Copy of `out/kt-video.mp4`: 1920×1080, 30 fps, H.264 CRF 20 `yuv420p`, AAC 160 kbps, `+faststart` |
| `out/captions.srt` | Captions on the final timeline. Subtitles aren't burned into the video. |
| `out/chapters.txt` | YouTube-style chapter timestamps |

Everything in `out/` and `audio/` is ignored by git and can be rebuilt.

## Files

| File | Role |
|---|---|
| `outline.md`, `script.md` | Approved outline and script. **`script.md` is the narration source**: `tts.py` reads the `> ` lines under each `### Narration`. |
| `facts.py` → `facts.json` | Pulls the values and code excerpts the video shows from `results/results.json`, `data/` and the source files. It fails if an excerpt's first line moved. |
| `tts.py` → `timing.json` | Kokoro voiceover → `audio/scene_XX.wav`, scene, sentence and word timestamps, captions and chapters. Each scene lasts its audio length plus 0.6 s. |
| `composition.src.html` | All 8 scenes. `window.renderAt(seconds)` is a pure function of time: no CSS transitions, no `requestAnimationFrame` timing, no randomness. |
| `render.mjs` | Inlines data, fonts and images into `out/composition.html`. Then it renders frames into ffmpeg (no frame files on disk), joins the scene WAVs with their padding, normalizes loudness and muxes. |
| `assets/ui/` | Two real UI screenshots (synthetic data), plus element rectangles for highlights |
| `assets/fonts/` | Space Grotesk (titles), Inter (body), JetBrains Mono (code), all OFL and inlined at build time |

## Setup (once)

```bash
cd docs/kt-video
npm install                                   # playwright 1.57.0 + fonts
npx playwright install chromium               # only if that Chromium build isn't installed yet
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-tts.txt   # .venv/bin/python on macOS/Linux
```

**ffmpeg** must be on `PATH`.

**espeak-ng** doesn't need a system install. Kokoro's phonemizer uses the library bundled in `espeakng-loader`. If you want a system copy, it's `winget install eSpeak-NG.eSpeak-NG` on Windows or `apt install espeak-ng` on Linux.

**First run** downloads the Kokoro-82M weights (Hugging Face) and spaCy's `en_core_web_sm`. Synthesis then runs locally.

## Rebuild

From the repo root:

```bash
make kt-video           # = facts.py → tts.py → render.mjs   (KT_PY=.venv/bin/python on macOS/Linux)
# or, inside docs/kt-video:  npm run kt-video
```

- **Render time:** about 5 minutes for the frames.
- **Audio cache:** sentence audio is cached in `audio/cache/`, so only edited sentences are re-synthesized.
- **Size limit:** the render aborts if the MP4 reaches 20 MB. Raise `KT_CRF`, e.g. `KT_CRF=23 node render.mjs`.

## Edit a scene

1. **Words.** Edit the `> ` narration lines for that scene in `script.md`.
   - Spell acronyms the way they should be spoken (`A-P-I`, `L-L-M`).
   - Add a matching entry to `CAPTION_SUBS` in `tts.py` so captions show the normal spelling.
2. **Visual beats.** In `composition.src.html`, beats are tied to spoken phrases with `at(scene, "phrase")`, using Kokoro's word timestamps.
   - If you remove a phrase that a beat uses, the build stops with `beat phrase not found`. Update the beat to a phrase that still exists.
3. **Preview.** `node render.mjs --preview`, then open `out/composition.html#preview`. It has play and scrub controls, with audio from `audio/narration.wav`.
4. **Check stills.** `node render.mjs --qa` writes stills to `out/stills/`: the middle and end of every scene, plus the code-focus beats. It also checks two things:
   - every scene renders byte-identically regardless of render order;
   - crossfades never dip to an empty frame.
5. **Render.** `make kt-video`.

**If the app's results or code change,** rerun `facts.py` (it's part of `make kt-video`). The video picks up the new numbers and excerpts automatically. Update the narration if a spoken number changed. If the UI changed, retake `assets/ui/summary.png` and `matrix.png`.

## Honesty constraints baked in

- Results are stated only for the 96 synthetic cases, from a mock-judge run with K = 5.
- The hardened graders' 0 / 0 is stated as true by construction.
- Flakiness is described as simulated (a seeded clock).
- The real LLM judge path is described as not exercised.
- Independent prototype, not affiliated with HUD. This is shown on every scene.
