// Capture the real Grader Audit UI for the KT video.
//
// Prerequisite (separate, explicit step): the app is running in mock mode, e.g.
//   env -u JUDGE_MODEL python -m audit.serve --port 8000
// This script refuses to capture unless /api/results equals snapshot/results.json, so the
// screenshots can never silently show different numbers from the narration.
//
// Usage: node capture.mjs [--url http://localhost:8000]

import { chromium } from "playwright";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { isDeepStrictEqual } from "node:util";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, "assets", "ui");
const URL_ARG = process.argv.indexOf("--url");
const BASE = URL_ARG > 0 ? process.argv[URL_ARG + 1] : "http://localhost:8000";
const VIEWPORT = { width: 1440, height: 900 };
const SCALE = 2;

mkdirSync(OUT, { recursive: true });
const snapshotText = readFileSync(join(HERE, "snapshot", "results.json"), "utf8");
const snapshot = JSON.parse(snapshotText);

const live = await (await fetch(`${BASE}/api/results`)).json();
if (!isDeepStrictEqual(live, snapshot)) {
  console.error("ABORT: live /api/results differs from snapshot/results.json. Not capturing.");
  process.exit(1);
}
if (live.meta.judge_backend !== "mock") {
  console.error(`ABORT: judge backend is ${live.meta.judge_backend}, expected mock.`);
  process.exit(1);
}

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: SCALE, colorScheme: "dark" });
const page = await context.newPage();
await page.goto(BASE, { waitUntil: "networkidle" });
await page.waitForSelector("#caseView .tid");
await page.evaluate(() => document.fonts.ready);

const manifest = {
  source: BASE,
  snapshot_sha256: createHash("sha256").update(snapshotText).digest("hex"),
  viewport: VIEWPORT,
  device_scale_factor: SCALE,
  color_scheme: "dark",
  captures: {},
};

// Rects of `selectors` relative to `root`, in CSS pixels.
async function rects(root, selectors) {
  return page.evaluate(([rootSel, sels]) => {
    const r = document.querySelector(rootSel).getBoundingClientRect();
    const out = {};
    for (const [name, sel] of Object.entries(sels)) {
      const el = typeof sel === "string" ? document.querySelector(sel) : null;
      if (!el) { out[name] = null; continue; }
      const b = el.getBoundingClientRect();
      out[name] = { x: b.left - r.left, y: b.top - r.top, w: b.width, h: b.height };
    }
    return out;
  }, [root, selectors]);
}

async function shoot(name, rootSel, selectors = {}) {
  // Full-page capture at scroll 0 so the sticky nav stays in its own place instead of overlapping
  // the element, and the mouse is parked so no hover outline leaks into the picture.
  await page.mouse.move(1, 1);
  await page.evaluate(() => window.scrollTo(0, 0));
  const box = await page.evaluate((sel) => {
    const b = document.querySelector(sel).getBoundingClientRect();
    return { x: b.left, y: b.top, width: b.width, height: b.height };
  }, rootSel);
  const file = `${name}.png`;
  await page.screenshot({ path: join(OUT, file), fullPage: true, clip: box, animations: "disabled" });
  manifest.captures[name] = { file, root: rootSel, w: box.width, h: box.height, rects: await rects(rootSel, selectors) };
  console.log(`captured ${file} (${Math.round(box.width)}x${Math.round(box.height)} css px)`);
}

async function openCase(probe, grader, taskId) {
  await page.click(`button.cell[data-p="${probe}"][data-g="${grader}"]`);
  await page.click(`button.crow[data-t="${taskId}"][data-p="${probe}"]`);
  await page.waitForFunction(([t, p]) => {
    const head = document.querySelector("#caseView .case-head");
    return head && head.textContent.includes(t) && head.textContent.includes(`probe: ${p}`);
  }, [taskId, probe]);
}

const caseSel = {
  instr: "#caseView .instr",
  naive: "#caseView .vcard:nth-of-type(1)",
  hardened: "#caseView .vcard:nth-of-type(2)",
  naive_runs: "#caseView .vcard:nth-of-type(1) .runs",
  output: "#caseView .io > div:nth-child(1)",
  gold: "#caseView .io > div:nth-child(2)",
  diff: "#caseView .diff",
};

// 1. Summary (default page state).
await shoot("summary", "#summary", {
  naive_card: "#cards .gcard:nth-child(1)",
  hardened_card: "#cards .gcard:nth-child(2)",
  naive_fp: "#cards .gcard:nth-child(1) .metric:nth-child(1)",
  naive_fn: "#cards .gcard:nth-child(1) .metric:nth-child(2)",
  naive_flaky: "#cards .gcard:nth-child(1) .metric:nth-child(3)",
  headline: "#headline",
});

// 2. Matrix with the default selection (substring_trap × naive), and 3. its first case (A1).
await openCase("substring_trap", "naive", "A1_null_customer_ids");
await shoot("matrix", "#matrix .split", {
  heatmap: "#matrixTable",
  cell_trap_naive: 'button.cell[data-p="substring_trap"][data-g="naive"]',
  naive_col_head: "#matrixTable tr:first-child th:nth-child(3)",
  case_list: "#caseList",
  row_A1: 'button.crow[data-t="A1_null_customer_ids"]',
});
await shoot("case_A1_substring_trap", "#caseView", caseSel);

// 4. Table false positive with diff.
await openCase("partial", "naive", "T4_revenue_by_region");
await shoot("case_T4_partial", "#caseView", caseSel);

// 5. False negative.
await openCase("paraphrase", "naive", "A2_completed_revenue");
await shoot("case_A2_paraphrase", "#caseView", caseSel);

// 6. Order matters (T5 shuffled).
await openCase("shuffled", "naive", "T5_top_customers");
await shoot("case_T5_shuffled", "#caseView", caseSel);

// 7. Flaky case (S1 gold).
await openCase("gold", "naive", "S1_finalize_run");
await shoot("case_S1_gold", "#caseView", caseSel);

// 8. Report panel: top (download button + summary), then scrolled to the flaky table.
// data-kt attributes only mark elements for measuring; they do not change what is rendered.
await page.evaluate(() => {
  const body = document.querySelector("#reportBody");
  body.scrollTop = 0;
  const section = (title) => {
    const h = [...body.querySelectorAll("h2")].find((e) => e.textContent.trim() === title);
    let el = h.nextElementSibling;
    while (el && el.tagName !== "TABLE") el = el.nextElementSibling;
    return { h, table: el };
  };
  const s = section("Summary");
  s.table.setAttribute("data-kt", "summary-table");
  const f = section("Flaky verdicts");
  f.h.setAttribute("data-kt", "flaky-heading");
  f.table.setAttribute("data-kt", "flaky-table");
});
await shoot("report_top", "#report .panel", { download: "#report .btn", summary_table: '[data-kt="summary-table"]' });
await page.evaluate(() => {
  const body = document.querySelector("#reportBody");
  const h = body.querySelector('[data-kt="flaky-heading"]');
  body.scrollTop = h.offsetTop - body.offsetTop - 8;
});
await shoot("report_flaky", "#report .panel", {
  flaky_heading: '[data-kt="flaky-heading"]', flaky_table: '[data-kt="flaky-table"]',
});

// The download endpoint really serves the report as an attachment.
const dl = await fetch(`${BASE}/report.md`);
manifest.report_download = {
  status: dl.status,
  content_disposition: dl.headers.get("content-disposition"),
  matches_snapshot_report:
    (await dl.text()) === readFileSync(join(HERE, "snapshot", "report.md"), "utf8"),
};

writeFileSync(join(OUT, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
await browser.close();
console.log("manifest written; report download:", manifest.report_download);
