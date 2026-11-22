// Takes the screenshots listed in ../ZRZUTY-EKRANU.md against the running stack (http://localhost:8080).
import { chromium } from "../../web/node_modules/@playwright/test/index.mjs";
import { readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "../..");
const out = join(root, "submission/slides/img");
const docs = (n, file) => {
  const dir = readdirSync(join(root, "Docs")).find((d) => d.startsWith(`${n}.`));
  return join(root, "Docs", dir, file);
};
const only = process.argv[2];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1366, height: 768 } });
const shot = (name) => page.screenshot({ path: join(out, `${name}.png`) });
const done = (n) => page.getByRole("region", { name: "Kolejka plików" }).getByText("Gotowe", { exact: true }).nth(n - 1).waitFor({ timeout: 300000 });

await page.goto("http://localhost:8080");
await shot("ekran-start");
await page.getByLabel("Wybierz pliki").setInputFiles([
  docs(3, "Wniosek o wydanie zaświadczenia.pdf"),
  docs(4, readdirSync(join(root, "Docs", readdirSync(join(root, "Docs")).find((d) => d.startsWith("4.")))).find((f) => f.endsWith(".pdf"))),
  docs(6, "Wniosek o wydanie zezwolenia na zajęcie pasa drogowego.pdf"),
]);
await page.waitForTimeout(3000);
await shot("ekran-kolejka-w-trakcie");
await done(3);
await shot("ekran-kolejka");
const result = page.getByRole("region", { name: /^Wynik:/ });
await result.scrollIntoViewIfNeeded();
await shot("ekran-weryfikacja");
await result.getByRole("tab", { name: "JSON" }).click();
await result.scrollIntoViewIfNeeded();
await shot("ekran-json");
await result.getByRole("tab", { name: "Raport" }).click();
await result.scrollIntoViewIfNeeded();
await shot("ekran-raport");
await page.goto("http://localhost:8080");
await page.getByLabel("Wybierz pliki").setInputFiles({ name: "notatki.txt", mimeType: "text/plain", buffer: Buffer.from("x") });
await page.waitForTimeout(500);
await shot("ekran-blad");
await browser.close();
