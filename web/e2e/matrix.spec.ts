import {
  appendFileSync,
  existsSync,
  readdirSync,
  readFileSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { basename, extname, join } from "node:path";
import { expect, type Page, test } from "@playwright/test";
import { pace, walkForm, watchErrors } from "./helpers";

// Run with `npm run e2e:matrix` (needs the stack on :8080; a full run takes tens of minutes).
const REPO_DOCS = "../Docs";
const ACCEPTED = new Set([
  ".pdf",
  ".doc",
  ".docx",
  ".ods",
  ".xlsx",
  ".jpg",
  ".jpeg",
  ".jpe",
  ".png",
]);
// Generous: the model may need ~60 s, a 429 adds a 60 s wait, big rasters add OCR time.
const ANALYSIS_TIMEOUT = 420_000;

interface Row {
  folder: number;
  file: string;
  format: string;
  sizeKB: number;
  status: "ok" | "blad" | "odrzucony" | "awaria";
  uiMs: number;
  apiMs: number | null;
  limited429: number;
  mode: string;
  fields: number | null;
  lint: string;
  steps: number | null;
  walk: string;
  note: string;
}
// A failing test restarts the worker, so rows live in a file, not in module state.
// `npm run e2e:matrix` deletes it first; a partial run (-g) updates only its own rows.
const ROWS_FILE = "test-results/matrix-rows.jsonl";

const samples: { folder: number; path: string }[] = [];
for (const dir of readdirSync(REPO_DOCS).sort()) {
  const folder = Number(/^(\d+)\./.exec(dir)?.[1]);
  if (!(folder >= 3 && folder <= 9)) continue;
  for (const f of readdirSync(join(REPO_DOCS, dir)).sort()) {
    if (/wizualizacja/i.test(f) || extname(f).toLowerCase() === ".json") continue;
    samples.push({ folder, path: join(REPO_DOCS, dir, f) });
  }
}

const fmt = (path: string) => extname(path).slice(1).toUpperCase();

function median(xs: number[]) {
  const s = [...xs].sort((a, b) => a - b);
  return s.length ? (s[Math.floor(s.length / 2)] ?? 0) : 0;
}

function writeResults() {
  if (!existsSync(ROWS_FILE)) return;
  const latest = new Map<string, Row>();
  for (const line of readFileSync(ROWS_FILE, "utf8").split("\n").filter(Boolean)) {
    const r: Row = JSON.parse(line);
    latest.set(`${r.folder}/${r.file}`, r);
  }
  const rows = [...latest.values()];
  const byFormat = new Map<string, Row[]>();
  for (const r of rows) byFormat.set(r.format, [...(byFormat.get(r.format) ?? []), r]);
  const formats = [...byFormat.entries()].map(([format, rs]) => ({
    format,
    files: rs.length,
    ok: rs.filter((r) => r.status === "ok").length,
    walkOk: rs.filter((r) => r.walk === "do końca").length,
    medianUiS: Math.round(median(rs.filter((r) => r.status === "ok").map((r) => r.uiMs)) / 1000),
    maxUiS: Math.round(Math.max(0, ...rs.map((r) => r.uiMs)) / 1000),
  }));
  writeFileSync(
    "e2e/results.json",
    `${JSON.stringify({ generated: new Date().toISOString(), formats, rows }, null, 2)}\n`,
  );
  const md = [
    "# Wyniki macierzy E2E (generowane, nie edytuj)",
    "",
    `Wygenerowano: ${new Date().toISOString()}. Źródło: \`npm run e2e:matrix\`, dane w \`results.json\`.`,
    "",
    "## Spójność formatów",
    "",
    "| Format | Plików | Gotowe | E-formularz do końca | Mediana [s] | Maks. [s] |",
    "|---|---:|---:|---:|---:|---:|",
    ...formats.map(
      (f) => `| ${f.format} | ${f.files} | ${f.ok} | ${f.walkOk} | ${f.medianUiS} | ${f.maxUiS} |`,
    ),
    "",
    "## Pliki",
    "",
    "| Folder | Plik | Stan | Czas [s] | Tryb | Pola | Kontrola | Kroki | Przejście | Uwagi |",
    "|---:|---|---|---:|---|---:|---|---:|---|---|",
    ...rows.map(
      (r) =>
        `| ${r.folder} | ${r.file} (${r.sizeKB} KB) | ${r.status} | ${Math.round(r.uiMs / 1000)} | ${r.mode} | ${r.fields ?? ""} | ${r.lint} | ${r.steps ?? ""} | ${r.walk} | ${r.note.replace(/\|/g, "/")} |`,
    ),
    "",
  ].join("\n");
  writeFileSync("e2e/RESULTS.md", md);
}

test.afterAll(writeResults);

for (const sample of samples) {
  const name = basename(sample.path);
  test(`@matrix ${sample.folder}: ${name}`, async ({ page }) => {
    test.setTimeout(ANALYSIS_TIMEOUT + 180_000);
    const { errors, limited } = watchErrors(page);
    const row: Row = {
      folder: sample.folder,
      file: name,
      format: fmt(sample.path),
      sizeKB: Math.round(statSync(sample.path).size / 1024),
      status: "awaria",
      uiMs: 0,
      apiMs: null,
      limited429: 0,
      mode: "",
      fields: null,
      lint: "",
      steps: null,
      walk: "",
      note: "",
    };
    try {
      await page.goto("/");
      let started = 0;
      page.on("request", (r) => {
        if (r.method() === "POST" && r.url().includes("/api/")) started = Date.now();
      });
      page.on("response", (r) => {
        if (r.request().method() === "POST" && r.status() === 200) row.apiMs = Date.now() - started;
      });

      await page.getByLabel("Wybierz pliki").setInputFiles(sample.path);
      if (!ACCEPTED.has(extname(sample.path).toLowerCase())) {
        // The browser rejects the extension before any upload; it must say so in Polish.
        const alert = page.getByRole("alert").filter({ hasText: "Nie dodano" });
        await expect(alert).toBeVisible();
        row.status = "odrzucony";
        row.note = (await alert.innerText()).replace(/\s+/g, " ");
        row.walk = "-";
        return;
      }
      await pace(page);
      const t0 = Date.now();
      const queue = page.getByRole("region", { name: "Kolejka plików" });
      await expect(queue.getByText(/^(Gotowe|Błąd)$/)).toBeVisible({ timeout: ANALYSIS_TIMEOUT });
      row.uiMs = Date.now() - t0;
      row.limited429 = limited.count;

      if (await queue.getByText(/^Błąd$/).count()) {
        row.status = "blad";
        row.note = (await queue.locator("tbody tr").first().innerText()).replace(/\s+/g, " ");
        row.walk = "-";
        expect(row.note, "an error must come with a Polish message").toMatch(/[a-ząćęłńóśźż]{4}/i);
        return;
      }
      row.status = "ok";

      const result = page.getByRole("region", { name: /^Wynik:/ });
      for (const tab of ["Dokument i formularz", "JSON", "Raport"]) {
        await expect(result.getByRole("tab", { name: tab })).toBeVisible();
      }
      const panel = result.getByRole("tabpanel");

      // JSON tab: parses, has a FINISH page.
      await result.getByRole("tab", { name: "JSON" }).click();
      const form = JSON.parse(await panel.locator("pre").innerText());
      expect(form.tabs.some((t: { type: string }) => t.type === "FINISH")).toBe(true);

      // Raport tab: mode and lint summary.
      await result.getByRole("tab", { name: "Raport" }).click();
      const summary = (await panel.getByText(/^Tryb:/).innerText()).replace(/\s+/g, " ");
      expect(summary).toMatch(/Tryb: (model językowy|reguły)/);
      expect(summary).toMatch(/Kontrola/);
      row.mode = /model/.test(summary) ? "model" : "reguły";
      row.fields = Number(/Rozpoznano (\d+)/.exec(summary)?.[1]);
      row.lint = /Kontrola: (.*?)\./.exec(summary)?.[1] ?? "brak uwag";

      // E-form: first step has an h1, "Dalej" walks to the FINISH summary.
      await result.getByRole("tab", { name: "Dokument i formularz" }).click();
      const walked = await walkForm(page, panel);
      row.steps = walked.steps;
      row.walk = walked.blockedAt ? `zablokowane na: ${walked.blockedAt}` : "do końca";
      expect(walked.blockedAt, `Dalej blocked at "${walked.blockedAt}"`).toBeNull();
    } finally {
      row.limited429 = Math.max(row.limited429, limited.count);
      if (errors.length) row.note = `${row.note} błędy konsoli: ${errors.length}`.trim();
      appendFileSync(ROWS_FILE, `${JSON.stringify(row)}\n`);
      expect(errors, "console and page errors").toEqual([]);
    }
  });
}

const small = [
  [3, "Wniosek o wydanie zaświadczenia.ods"],
  [3, "Wniosek o wydanie zaświadczenia.xlsx"],
  [3, "Wniosek o wydanie zaświadczenia.docx"],
  [3, "Wniosek o wydanie zaświadczenia.doc"],
  [3, "Wniosek o wydanie zaświadczenia.pdf"],
  [4, "Wniosek o wynajęcie świetlicy.xlsx"],
  [4, "Wniosek o wynajęcie świetlicy.docx"],
  [4, "Wniosek o wynajęcie świetlicy.doc"],
  [4, "Wniosek o wynajęcie świetlicy.pdf"],
  [6, "Wniosek o wydanie zezwolenia na zajęcie pasa drogowego.docx"],
  [6, "Wniosek o wydanie zezwolenia na zajęcie pasa drogowego.xlsx"],
  [6, "Wniosek o wydanie zezwolenia na zajęcie pasa drogowego.ods"],
].flatMap(([folder, file]) => {
  const dir = samples.find((s) => s.folder === folder)?.path;
  return dir ? [join(dir, "..", String(file))] : [];
});

const SMALL_PDF = small[4] ?? "";

test("@matrix batch 12 plików: ponawianie po 429 działa end to end", async ({ page, request }) => {
  test.setTimeout(1_800_000);
  const { errors, limited } = watchErrors(page);
  // Spend the rate limit first: junk POSTs are counted by nginx before the API sees them.
  const statuses: number[] = [];
  for (let i = 0; i < 12; i++) {
    const r = await request.post("/api/v1/forms", {
      multipart: { file: { name: "prime.txt", mimeType: "text/plain", buffer: Buffer.from("x") } },
    });
    statuses.push(r.status());
  }
  expect(statuses, "priming must hit the limit").toContain(429);

  await page.goto("/");
  await page.getByLabel("Wybierz pliki").setInputFiles(small);
  const queue = page.getByRole("region", { name: "Kolejka plików" });
  await expect(queue.locator("tbody tr")).toHaveCount(small.length);
  await expect(queue.getByText("Czeka na limit").first()).toBeVisible({ timeout: 90_000 });
  await expect
    .poll(async () => queue.getByText(/^(Gotowe|Błąd)$/).count(), {
      timeout: 1_500_000,
      intervals: [5_000],
    })
    .toBe(small.length);
  const done = await queue.getByText(/^Gotowe$/).count();
  const failed = await queue.getByText(/^Błąd$/).count();
  test.info().annotations.push({
    type: "batch",
    description: `Gotowe ${done}, Błąd ${failed}, 429 w konsoli ${limited.count}, primer ${statuses.join(",")}`,
  });
  expect(limited.count).toBeGreaterThan(0);
  expect(done).toBe(small.length);
  expect(errors).toEqual([]);
});

test("@matrix API niedostępne: polski komunikat, reszta interfejsu działa", async ({ page }) => {
  const { errors } = watchErrors(page, [/Failed to load resource|net::ERR/]);
  await page.route("**/api/**", (r) => r.abort());
  await page.goto("/");
  await page.getByLabel("Wybierz pliki").setInputFiles(SMALL_PDF);
  const queue = page.getByRole("region", { name: "Kolejka plików" });
  await expect(queue.getByText(/^Błąd$/)).toBeVisible({ timeout: 30_000 });
  await expect(queue).toContainText("Nie można połączyć się z usługą");
  // The rest still works: sample data, the three tabs, the preview link.
  await page.getByRole("button", { name: "Wczytaj dane przykładowe" }).click();
  const result = page.getByRole("region", { name: /^Wynik:/ });
  await expect(result.getByRole("tab", { name: "JSON" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Podgląd pliku JSON" })).toBeVisible();
  expect(errors).toEqual([]);
});

/** Presses Tab until the focused element satisfies `test`; fails after `max` presses. */
async function tabTo(page: Page, test: string, max = 80) {
  for (let i = 0; i < max; i++) {
    await page.keyboard.press("Tab");
    const hit = await page.evaluate((sel) => document.activeElement?.matches(sel) ?? false, test);
    if (hit) return;
  }
  throw new Error(`Tab never reached ${test}`);
}

test("@matrix klawiatura: wgranie, wybór i przejście przez zakładki wyniku", async ({ page }) => {
  test.setTimeout(ANALYSIS_TIMEOUT + 60_000);
  const { errors } = watchErrors(page);
  await page.goto("/");
  await tabTo(page, 'input[type="file"]'); // the real, visually hidden input is focusable
  // The OS file dialog cannot be driven; hand the file to the focused input.
  await page.locator('input[type="file"]:focus').setInputFiles(SMALL_PDF);
  const queue = page.getByRole("region", { name: "Kolejka plików" });
  await expect(queue.getByText(/^Gotowe$/)).toBeVisible({ timeout: ANALYSIS_TIMEOUT });
  const result = page.getByRole("region", { name: /^Wynik:/ });
  await expect(result).toBeVisible();

  // Select the file from the queue with the keyboard.
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  await tabTo(page, "table button");
  await page.keyboard.press("Enter");
  await expect(queue.locator("tr[aria-current=true]")).toHaveCount(1);

  // Into the tablist and across the three tabs with arrow keys.
  await tabTo(page, '[role="tab"][aria-selected="true"]');
  await page.keyboard.press("ArrowRight");
  await expect(result.getByRole("tab", { name: "JSON", selected: true })).toBeFocused();
  await expect(result.getByRole("tabpanel")).toContainText('"tabs"');
  await page.keyboard.press("ArrowRight");
  await expect(result.getByRole("tab", { name: "Raport", selected: true })).toBeFocused();
  await expect(result.getByRole("tabpanel")).toContainText("Tryb:");
  await page.keyboard.press("ArrowRight");
  await expect(
    result.getByRole("tab", { name: "Dokument i formularz", selected: true }),
  ).toBeFocused();
  expect(errors).toEqual([]);
});

for (const [label, file] of [
  ["Przykład 1", "przyklad-1.json"],
  ["Przykład 5", "przyklad-5.json"],
] as const) {
  test(`@matrix /podglad: ${file} do ekranu końcowego`, async ({ page }) => {
    test.setTimeout(240_000);
    const { errors } = watchErrors(page);
    await page.goto("/podglad");
    await page.getByRole("button", { name: label }).click();
    await expect(page.locator("main h1").first()).toBeVisible();
    const walked = await walkForm(page, page.locator("main"));
    test.info().annotations.push({ type: "kroki", description: walked.titles.join(" > ") });
    expect(walked.blockedAt, `Dalej blocked at "${walked.blockedAt}"`).toBeNull();
    expect(errors).toEqual([]);
  });
}
