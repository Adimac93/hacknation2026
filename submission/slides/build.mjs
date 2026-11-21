// Renders slides.html to Biurokratka-prezentacja.pdf (1920x1080, 10 pages).
// Playwright is not a dependency of web/; install it without touching package files:
//   cd web && npm i --no-save playwright && npx playwright install chromium
// Run: node submission/slides/build.mjs
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(here, "../../web/package.json"));
const { chromium } = require("playwright");

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
await page.goto(pathToFileURL(path.join(here, "slides.html")).href, { waitUntil: "load" });
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(500); // let screenshot slots settle
const out = path.join(here, "Biurokratka-prezentacja.pdf");
await page.pdf({
  path: out,
  width: "1920px",
  height: "1080px",
  printBackground: true,
  preferCSSPageSize: true,
});
await browser.close();
console.log("written", out);
