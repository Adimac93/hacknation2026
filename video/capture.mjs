// Screenshots for the pitch video, taken from the running service (default: the public demo).
// Run from the repo root: node video/capture.mjs [URL]. Uses Playwright from web/node_modules.
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "../web/node_modules/@playwright/test/index.mjs";

const url = process.argv[2] ?? "https://formularze.heckyeah.pl";
const out = join(dirname(fileURLToPath(import.meta.url)), "public/zrzuty");
mkdirSync(out, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 2 });
const shot = (name, opts = {}) => page.screenshot({ path: join(out, `${name}.png`), ...opts });
const queue = () => page.getByRole("region", { name: "Kolejka plików" });

await page.goto(url);
await page.waitForLoadState("networkidle");
await shot("01-start");

await page.getByText("Przykładowe blankiety z materiałów COI").click();
await page.getByRole("button", { name: /^PDF: Wniosek o wydanie zezwolenia na zajęcie pasa/ }).waitFor();
await page.getByText("Przykładowe blankiety z materiałów COI").scrollIntoViewIfNeeded();
await shot("02-przyklady");

await page.getByRole("button", { name: /^PDF: Wniosek o wydanie zezwolenia na zajęcie pasa/ }).click();
await page.waitForTimeout(2500);
await queue().scrollIntoViewIfNeeded();
await shot("03-analiza");
await queue().getByText("Gotowe", { exact: true }).first().waitFor({ timeout: 180000 });
await shot("04-gotowe");

const result = page.getByRole("region", { name: /^Wynik:/ });
await result.scrollIntoViewIfNeeded();
const select = page.getByLabel("Pokaż źródło pola");
const options = await select.locator("option").all();
const pick = options[Math.min(8, options.length - 1)];
await select.selectOption({ index: Math.min(8, options.length - 1) });
await page.waitForTimeout(500);
await select.scrollIntoViewIfNeeded();
await shot("05-zrodlo-pola");
await page.mouse.wheel(0, 500);
await page.waitForTimeout(400);
await shot("06-podglad");

await result.getByRole("tab", { name: "JSON" }).click();
await result.scrollIntoViewIfNeeded();
await page.waitForTimeout(400);
await shot("07-json");
await result.getByRole("tab", { name: "Raport" }).click();
await result.scrollIntoViewIfNeeded();
await page.waitForTimeout(400);
await shot("08-raport");

await page.goto(url);
await page.getByLabel("Wybierz pliki").setInputFiles({ name: "notatki.txt", mimeType: "text/plain", buffer: Buffer.from("x") });
await page.waitForTimeout(600);
await shot("09-blad");

writeFileSync(join(out, "README.md"), `Zrzuty z ${url}, ${new Date().toISOString()}, viewport 1600x900 @2x. Źródło: video/capture.mjs.\n`);
console.log(`saved to ${out}; picked field: ${await pick.textContent()}`);
await browser.close();
