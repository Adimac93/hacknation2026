import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, test } from "@playwright/test";

// Paths are relative to the repo root; the suite is run from web/.
const DOCS = "../Docs/3. Wniosek o wydanie zaświadczenia - formularze do cyfryzacji";
const PDF = `${DOCS}/Wniosek o wydanie zaświadczenia.pdf`;
const PNG = `${DOCS}/Wniosek o wydanie zaświadczenia.png`;

test.beforeEach(async ({ page }) => {
  await page.goto("/");
});

test("PDF: kolejka kończy się statusem Gotowe i pojawia się wynik", async ({ page }) => {
  await page.getByLabel("Wybierz pliki").setInputFiles(PDF);
  const queue = page.getByRole("region", { name: "Kolejka plików" });
  await expect(queue.getByText("Gotowe")).toBeVisible();
  const result = page.getByRole("region", { name: /^Wynik:/ });
  for (const name of ["Dokument i formularz", "JSON", "Raport"]) {
    await expect(result.getByRole("tab", { name })).toBeVisible();
  }
  await result.getByRole("tab", { name: "JSON" }).click();
  await expect(result.getByRole("tabpanel")).toContainText(/tabs/);
});

test("PNG: Gotowe albo widoczny błąd, bez awarii strony", async ({ page }) => {
  const crashes: Error[] = [];
  page.on("pageerror", (e) => crashes.push(e));
  await page.getByLabel("Wybierz pliki").setInputFiles(PNG);
  const queue = page.getByRole("region", { name: "Kolejka plików" });
  await expect(queue.getByText(/^(Gotowe|Błąd)$/)).toBeVisible();
  expect(crashes).toEqual([]);
});

test("niedozwolone pliki są odrzucane w przeglądarce", async ({ page }) => {
  const dir = mkdtempSync(join(tmpdir(), "e2e-"));
  const bad = [join(dir, "bad;name.pdf"), join(dir, "x.exe")];
  for (const f of bad) writeFileSync(f, "x");
  let uploads = 0;
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().includes("/api/")) uploads++;
  });
  await page.getByLabel("Wybierz pliki").setInputFiles(bad);
  await expect(page.getByRole("alert").filter({ hasText: "Nie dodano" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Kolejka plików" })).toHaveCount(0);
  expect(uploads).toBe(0);
});

test("dane przykładowe tworzą wynik bez wywołania API", async ({ page }) => {
  const apiCalls: string[] = [];
  page.on("request", (r) => {
    if (r.url().includes("/api/")) apiCalls.push(r.url());
  });
  await page.getByRole("button", { name: "Wczytaj dane przykładowe" }).click();
  const result = page.getByRole("region", { name: /^Wynik:/ });
  await expect(result.getByRole("tab", { name: "JSON" })).toBeVisible();
  expect(apiCalls).toEqual([]);
});
