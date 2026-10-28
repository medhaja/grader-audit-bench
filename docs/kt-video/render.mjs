// Build the self-contained composition and render the KT video.
//
//   node render.mjs            build out/composition.html, render out/kt-video.mp4, copy it to ./kt-video.mp4
//   node render.mjs --preview  build only; open out/composition.html#preview in a browser
//   node render.mjs --qa       build, write a still from the middle of every scene (plus code-focus beats)
//                              to out/stills/, and check determinism and crossfades
//
// Inputs (made by facts.py and tts.py; never regenerated here): facts.json, timing.json, audio/scene_XX.wav,
// assets/ui/{summary,matrix}.png + manifest.json, assets/fonts/*.woff2.

import { chromium } from "playwright";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { copyFileSync, existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, "out");
const FPS = 30;
const CRF = process.env.KT_CRF || "20";
const MP4 = join(OUT, "kt-video.mp4");
const args = new Set(process.argv.slice(2));

const die = (msg) => { console.error(`ABORT: ${msg}`); process.exit(1); };
const read = (p) => readFileSync(p, "utf8");
const json = (p) => JSON.parse(read(p));
const safe = (obj) => JSON.stringify(obj).replace(/</g, "\\u003c");

function build() {
  mkdirSync(OUT, { recursive: true });
  const timing = json(join(HERE, "timing.json"));
  const facts = json(join(HERE, "facts.json"));
  const manifest = json(join(HERE, "assets", "ui", "manifest.json"));
  if (facts.meta.judge_backend !== "mock") die("facts.json is not from a mock-judge run");

  const assets = {};
  for (const f of ["summary.png", "matrix.png"]) {
    assets[f] = `data:image/png;base64,${readFileSync(join(HERE, "assets", "ui", f)).toString("base64")}`;
  }
  const font = (family, weight, file) => `@font-face { font-family: "${family}"; font-weight: ${weight}; font-style: normal;
  src: url(data:font/woff2;base64,${readFileSync(join(HERE, "assets", "fonts", file)).toString("base64")}) format("woff2"); }`;
  const fonts = [
    font("Space Grotesk", 500, "space-grotesk-latin-500-normal.woff2"),
    font("Space Grotesk", 700, "space-grotesk-latin-700-normal.woff2"),
    font("Inter", 400, "inter-latin-400-normal.woff2"), font("Inter", 500, "inter-latin-500-normal.woff2"),
    font("Inter", 600, "inter-latin-600-normal.woff2"), font("Inter", 700, "inter-latin-700-normal.woff2"),
    font("JetBrains Mono", 400, "jetbrains-mono-latin-400-normal.woff2"),
    font("JetBrains Mono", 500, "jetbrains-mono-latin-500-normal.woff2"),
  ].join("\n");
  const data = [`window.TIMING = ${safe(timing)};`, `window.FACTS = ${safe(facts)};`,
    `window.MANIFEST = ${safe(manifest)};`, `window.ASSETS = ${safe(assets)};`].join("\n");
  const html = read(join(HERE, "composition.src.html")).replace("/*__FONTS__*/", fonts).replace("/*__DATA__*/", data);
  const outHtml = join(OUT, "composition.html");
  writeFileSync(outHtml, html);
  console.log(`built ${outHtml} (${(html.length / 1e6).toFixed(1)} MB), duration ${timing.total}s`);
  return { outHtml, timing };
}

async function openPage(outHtml) {
  // Software raster, full repaints: frames must not depend on what was drawn before.
  const browser = await chromium.launch({ args: ["--disable-gpu", "--disable-gpu-compositing", "--disable-partial-raster", "--disable-lcd-text"] });
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
    const id = `s${String(sc.n).padStart(2, "0")}`;
    times.push([`${id}_mid`, (sc.start + sc.end) / 2], [`${id}_late`, sc.end - 0.8]);
    if (sc.n === 4) times.push([`${id}_token`, sc.start + 0.55 * (sc.end - sc.start)]);
  }
  // Code-focus scene 5: naive pane, then the hardened pane with each highlight group.
  const s5 = timing.scenes[4];
  for (const f of [0.18, 0.5, 0.62, 0.78, 0.9]) times.push([`s05_code_${Math.round(f * 100)}`, s5.start + f * (s5.end - s5.start)]);
  for (const [name, t] of times) writeFileSync(join(dir, `${name}.png`), await frame(page, t, "png"));

  // Determinism: for every scene, a mid-scene frame must be byte-identical before and after a detour
  // through other scenes (render order must not matter).
  const nondeterministic = [];
  for (const sc of timing.scenes) {
    const probe = sc.start + 0.6 * (sc.end - sc.start);
    const a = await frame(page, probe, "png");
    await frame(page, (probe + timing.total / 2) % timing.total, "png");
    await frame(page, Math.max(0, sc.start - 0.15), "png");
    const b = await frame(page, probe, "png");
    if (!a.equals(b)) nondeterministic.push(+probe.toFixed(2));
  }
  // Crossfades: total scene opacity must stay near 1 at every frame (no dip to an empty stage).
  let minSum = Infinity, minAt = 0;
  for (let i = 0; i <= Math.round(timing.total * FPS); i++) {
    const s = await page.evaluate((tt) => window.renderAt(tt), i / FPS);
    if (s < minSum) { minSum = s; minAt = i / FPS; }
  }
  await browser.close();
  if (errors.length) die(errors.join("\n"));
  const report = { stills: times.length, deterministic: nondeterministic.length === 0, nondeterministic, min_scene_opacity_sum: +minSum.toFixed(3), at: +minAt.toFixed(2) };
  writeFileSync(join(dir, "qa.json"), JSON.stringify(report, null, 2));
  console.log(report);
}

function run(argv) {
  return new Promise((res) => {
    const p = spawn("ffmpeg", argv, { stdio: ["ignore", "ignore", "pipe"] });
    let err = "";
    p.stderr.on("data", (d) => (err += d));
    p.on("close", (code) => res({ code, err }));
  });
}

// Concatenate audio/scene_XX.wav in order, each followed by its silent pad (timing.json), then apply
// two-pass EBU R128 loudness normalization (-16 LUFS). Level only: duration is unchanged.
async function buildAudio(timing) {
  const inputs = [], filters = [];
  timing.scenes.forEach((sc, i) => {
    const wav = join(HERE, "audio", `scene_${String(sc.n).padStart(2, "0")}.wav`);
    if (!existsSync(wav)) die(`${wav} missing; run tts.py first.`);
    inputs.push("-i", wav);
    const pad = +(sc.end - sc.start - sc.speech).toFixed(3);
    filters.push(`[${i}:a]apad=pad_dur=${pad}[p${i}]`);
  });
  const concat = `${filters.join(";")};${timing.scenes.map((_, i) => `[p${i}]`).join("")}concat=n=${timing.scenes.length}:v=0:a=1[a]`;
  const joined = join(HERE, "audio", "narration_joined.wav");
  let r = await run(["-y", "-hide_banner", "-loglevel", "error", ...inputs, "-filter_complex", concat, "-map", "[a]", joined]);
  if (r.code !== 0) die(`audio concat failed: ${r.err}`);
  const target = "I=-16:TP=-1.5:LRA=11";
  const m = await run(["-hide_banner", "-nostats", "-i", joined, "-af", `loudnorm=${target}:print_format=json`, "-f", "null", "-"]);
  const st = JSON.parse(m.err.slice(m.err.lastIndexOf("{"), m.err.lastIndexOf("}") + 1));
  const out = join(HERE, "audio", "narration_final.wav");
  const f = `loudnorm=${target}:measured_I=${st.input_i}:measured_TP=${st.input_tp}:measured_LRA=${st.input_lra}:measured_thresh=${st.input_thresh}:offset=${st.target_offset}:linear=true`;
  r = await run(["-y", "-hide_banner", "-loglevel", "error", "-i", joined, "-af", f, "-ar", "48000", out]);
  if (r.code !== 0) die(`loudnorm failed: ${r.err}`);
  console.log(`audio: ${timing.scenes.length} scenes joined, ${st.input_i} LUFS -> -16 LUFS`);
  return out;
}

async function render(outHtml, timing) {
  const wav = await buildAudio(timing);
  const nFrames = Math.round(timing.total * FPS);
  const { browser, page } = await openPage(outHtml);
  const ff = spawn("ffmpeg", ["-y", "-loglevel", "error",
    "-f", "image2pipe", "-framerate", String(FPS), "-c:v", "mjpeg", "-i", "pipe:0",
    "-i", wav, "-map", "0:v:0", "-map", "1:a:0",
    // JPEG frames are full range; convert to TV-range yuv420p (BT.709) so every player shows the same colors.
    "-vf", "scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p",
    "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
    "-c:v", "libx264", "-preset", "veryfast", "-crf", CRF, "-pix_fmt", "yuv420p", "-r", String(FPS),
    "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-shortest", "-movflags", "+faststart", MP4], { stdio: ["pipe", "inherit", "inherit"] });
  const t0 = Date.now();
  for (let i = 0; i < nFrames; i++) {
    const buf = await frame(page, i / FPS);
    if (!ff.stdin.write(buf)) await once(ff.stdin, "drain"); // backpressure: no frames on disk
    if (i % 900 === 0) console.log(`frame ${i}/${nFrames} (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
  }
  ff.stdin.end();
  const [code] = await once(ff, "close");
  await browser.close();
  if (code !== 0) die(`ffmpeg exited with ${code}`);
  const mb = statSync(MP4).size / 1e6;
  console.log(`wrote ${MP4}: ${nFrames} frames, ${mb.toFixed(1)} MB, CRF ${CRF}, in ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  if (mb >= 20) die("video is 20 MB or more; rerun with a higher KT_CRF");
  copyFileSync(MP4, join(HERE, "kt-video.mp4"));
  console.log(`copied to ${join(HERE, "kt-video.mp4")}`);
}

const { outHtml, timing } = build();
if (args.has("--preview")) console.log(`preview: ${pathToFileURL(outHtml).href}#preview`);
else if (args.has("--qa")) await qa(outHtml, timing);
else await render(outHtml, timing);
