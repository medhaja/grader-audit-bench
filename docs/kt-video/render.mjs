// Build the self-contained composition and render the KT video.
//
//   node render.mjs            build out/composition.html, render out/grader-audit-demo.mp4
//   node render.mjs --preview  build only; open out/composition.html#preview in a browser
//   node render.mjs --qa       build, write QA stills to out/stills/ and run a determinism check
//
// Inputs (never regenerated here): timing.json + audio/narration.wav (from tts.py),
// snapshot/results.json, assets/ui/* (from capture.mjs), evidence.json, the verified code excerpt.

import { chromium } from "playwright";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..", "..");
const OUT = join(HERE, "out");
const FPS = 30;
const MP4 = join(OUT, "grader-audit-demo.mp4");
const args = new Set(process.argv.slice(2));

const die = (msg) => { console.error(`ABORT: ${msg}`); process.exit(1); };
const read = (p) => readFileSync(p, "utf8");
const json = (p) => JSON.parse(read(p));
const safe = (obj) => JSON.stringify(obj).replace(/</g, "\\u003c");

function build() {
  mkdirSync(OUT, { recursive: true });
  const timing = json(join(HERE, "timing.json"));
  const snapshotText = read(join(HERE, "snapshot", "results.json"));
  const snapshot = JSON.parse(snapshotText);
  const manifest = json(join(HERE, "assets", "ui", "manifest.json"));
  const evidence = json(join(HERE, "evidence.json"));

  const sha = createHash("sha256").update(snapshotText).digest("hex");
  if (manifest.snapshot_sha256 !== sha) die("UI captures were taken against a different results snapshot.");
  if (snapshot.meta.judge_backend !== "mock") die("snapshot is not a mock-judge run.");

  // Verbatim code excerpt, checked against the recorded location.
  const ex = evidence.code_excerpt;
  const src = read(join(REPO, ex.file)).split(/\r?\n/);
  const lines = src.slice(ex.start - 1, ex.end);
  if (!lines[0].startsWith(ex.first_line_prefix)) die(`${ex.file}:${ex.start} no longer starts with ${ex.first_line_prefix}`);

  const tasks = {};
  for (const id of ["A1_null_customer_ids"]) tasks[id] = json(join(REPO, "data", "tasks", id, "task.json")).instruction;

  const results = {
    meta: { probes: snapshot.meta.probes, n_cases: snapshot.meta.n_cases, judge_backend: snapshot.meta.judge_backend },
    summary: snapshot.summary,
    judge_calls: snapshot.judge.log.length,
    cases: snapshot.cases.map((c) => ({
      task_id: c.task_id, probe: c.probe, should_pass: c.should_pass,
      verdicts: Object.fromEntries(Object.entries(c.verdicts).map(([g, v]) =>
        [g, { score: v.score, runs: v.runs, error: v.error, reason: v.reason }])),
    })),
  };

  const assets = {};
  for (const f of readdirSync(join(HERE, "assets", "ui")).filter((f) => f.endsWith(".png"))) {
    assets[f] = `data:image/png;base64,${readFileSync(join(HERE, "assets", "ui", f)).toString("base64")}`;
  }
  const font = (family, weight, file) => `@font-face { font-family: "${family}"; font-weight: ${weight}; font-style: normal;
  src: url(data:font/woff2;base64,${readFileSync(join(HERE, "assets", "fonts", file)).toString("base64")}) format("woff2"); }`;
  const fonts = [
    font("Inter", 400, "inter-latin-400-normal.woff2"), font("Inter", 500, "inter-latin-500-normal.woff2"),
    font("Inter", 600, "inter-latin-600-normal.woff2"), font("Inter", 700, "inter-latin-700-normal.woff2"),
    font("JetBrains Mono", 400, "jetbrains-mono-latin-400-normal.woff2"),
    font("JetBrains Mono", 500, "jetbrains-mono-latin-500-normal.woff2"),
  ].join("\n");

  const data = [
    `window.TIMING = ${safe(timing)};`, `window.RESULTS = ${safe(results)};`, `window.TASKS = ${safe(tasks)};`,
    `window.MANIFEST = ${safe(manifest)};`, `window.EVIDENCE = ${safe(evidence)};`,
    `window.CODE = ${safe({ file: ex.file, start: ex.start, lines })};`, `window.ASSETS = ${safe(assets)};`,
  ].join("\n");
  const html = read(join(HERE, "composition.src.html")).replace("/*__FONTS__*/", fonts).replace("/*__DATA__*/", data);
  const outHtml = join(OUT, "composition.html");
  writeFileSync(outHtml, html);
  console.log(`built ${outHtml} (${(html.length / 1e6).toFixed(1)} MB), duration ${timing.total}s`);
  return { outHtml, timing };
}

async function openPage(outHtml) {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  await page.goto(pathToFileURL(outHtml).href);
  await page.evaluate(() => window.ready);
  if (errors.length) die(`composition errors:\n${errors.join("\n")}`);
  return { browser, page, errors };
}

const frame = async (page, t, type = "jpeg") => {
  await page.evaluate((tt) => window.renderAt(tt), t);
  return page.screenshot(type === "png" ? { type: "png" } : { type: "jpeg", quality: 94 });
};

async function qa(outHtml, timing) {
  const { browser, page, errors } = await openPage(outHtml);
  const dir = join(OUT, "stills");
  mkdirSync(dir, { recursive: true });
  const times = [];
  for (const sc of timing.scenes) {
    times.push([`s${String(sc.n).padStart(2, "0")}_mid`, (sc.start + sc.end) / 2]);
    times.push([`s${String(sc.n).padStart(2, "0")}_late`, sc.end - 1.2]);
    if (sc.n > 1) times.push([`s${String(sc.n).padStart(2, "0")}_boundary`, sc.start]);
  }
  for (const [name, t] of times) writeFileSync(join(dir, `${name}.png`), await frame(page, t, "png"));
  // Determinism: the same time must give byte-identical frames regardless of render order.
  const probe = timing.scenes[4].start + 7.3;
  const a = await frame(page, probe, "png");
  await frame(page, 3.0, "png");
  const b = await frame(page, probe, "png");
  // Blank-frame scan at frame resolution: transitions pass through the background briefly by design;
  // flag any stretch where total scene opacity stays below 0.5 for longer than 0.25 s.
  const blank = [];
  let darkFrom = null, longestDark = 0;
  for (let i = 0; i <= Math.round(timing.total * FPS); i++) {
    const t = i / FPS;
    const sum = await page.evaluate((tt) => window.renderAt(tt), t);
    if (sum < 0.5) { if (darkFrom === null) darkFrom = t; }
    else if (darkFrom !== null) {
      const span = t - darkFrom; longestDark = Math.max(longestDark, span);
      if (span > 0.25) blank.push([+darkFrom.toFixed(2), +span.toFixed(2)]);
      darkFrom = null;
    }
  }
  await browser.close();
  if (errors.length) die(errors.join("\n"));
  const report = { stills: times.length, deterministic: a.equals(b), longest_dark_transition_s: +longestDark.toFixed(3), dark_spans_over_0_25s: blank };
  writeFileSync(join(dir, "qa.json"), JSON.stringify(report, null, 2));
  console.log(report);
}

// Two-pass EBU R128 loudness normalization (-16 LUFS, -1.5 dBTP). Level only: duration is unchanged.
async function normalizeAudio(src) {
  const run = (argv) => new Promise((res) => {
    const p = spawn("ffmpeg", argv, { stdio: ["ignore", "ignore", "pipe"] });
    let err = "";
    p.stderr.on("data", (d) => (err += d));
    p.on("close", (code) => res({ code, err }));
  });
  const target = "I=-16:TP=-1.5:LRA=11";
  const m = await run(["-hide_banner", "-nostats", "-i", src, "-af", `loudnorm=${target}:print_format=json`, "-f", "null", "-"]);
  const stats = JSON.parse(m.err.slice(m.err.lastIndexOf("{"), m.err.lastIndexOf("}") + 1));
  const out = join(HERE, "audio", "narration_loudnorm.wav");
  const f = `loudnorm=${target}:measured_I=${stats.input_i}:measured_TP=${stats.input_tp}:measured_LRA=${stats.input_lra}:measured_thresh=${stats.input_thresh}:offset=${stats.target_offset}:linear=true`;
  const r = await run(["-y", "-hide_banner", "-loglevel", "error", "-i", src, "-af", f, "-ar", "48000", out]);
  if (r.code !== 0) die(`loudnorm failed: ${r.err}`);
  console.log(`audio loudness ${stats.input_i} LUFS -> -16 LUFS target`);
  return out;
}

async function render(outHtml, timing) {
  const raw = join(HERE, "audio", "narration.wav");
  if (!existsSync(raw)) die("audio/narration.wav missing; run tts.py first.");
  const wav = await normalizeAudio(raw);
  const nFrames = Math.round(timing.total * FPS);
  const { browser, page } = await openPage(outHtml);
  const ff = spawn("ffmpeg", ["-y", "-loglevel", "error",
    "-f", "image2pipe", "-framerate", String(FPS), "-c:v", "mjpeg", "-i", "pipe:0",
    "-i", wav, "-map", "0:v:0", "-map", "1:a:0",
    // JPEG frames are full range; convert to standard TV-range yuv420p (BT.709) for players.
    "-vf", "scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p",
    "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", String(FPS),
    "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", MP4], { stdio: ["pipe", "inherit", "inherit"] });
  const t0 = Date.now();
  for (let i = 0; i < nFrames; i++) {
    const buf = await frame(page, i / FPS);
    if (!ff.stdin.write(buf)) await once(ff.stdin, "drain"); // backpressure
    if (i % 600 === 0) console.log(`frame ${i}/${nFrames} (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
  }
  ff.stdin.end();
  const [code] = await once(ff, "close");
  await browser.close();
  if (code !== 0) die(`ffmpeg exited with ${code}`);
  console.log(`wrote ${MP4}: ${nFrames} frames in ${((Date.now() - t0) / 1000).toFixed(0)}s`);
}

const { outHtml, timing } = build();
if (args.has("--preview")) console.log(`preview: ${pathToFileURL(outHtml).href}#preview`);
else if (args.has("--qa")) await qa(outHtml, timing);
else await render(outHtml, timing);
