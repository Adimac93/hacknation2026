import type { Locator, Page } from "@playwright/test";
import { expect } from "@playwright/test";

/**
 * Console errors and page errors of one page. A 429 from the rate limiter shows up in the
 * console as a failed resource load; it is expected (the UI retries) and counted separately.
 */
export function watchErrors(page: Page, ignore: RegExp[] = []) {
  const errors: string[] = [];
  const limited = { count: 0 };
  page.on("console", (m) => {
    if (m.type() !== "error") return;
    const text = m.text();
    if (/status of 429/.test(text)) {
      limited.count++;
      return;
    }
    if (ignore.some((re) => re.test(text))) return;
    errors.push(`console: ${text}`);
  });
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  return { errors, limited };
}

/** Keeps below the nginx limit: at most `perMinute` POSTs in any rolling minute. */
const posts: number[] = [];
export async function pace(page: Page, perMinute = 8) {
  const now = Date.now();
  while (posts.length > 0 && now - (posts[0] ?? 0) > 60_000) posts.shift();
  if (posts.length >= perMinute) {
    await page.waitForTimeout(60_000 - (now - (posts[0] ?? now)) + 500);
  }
  posts.push(Date.now());
}

const SAMPLE = {
  text: "Test",
  number: "10",
  date: "2000-01-15",
  pesel: "44051401359",
  nip: "5260250274",
  regon: "123456785",
  zip: "00-950",
  email: "jan.nowak@mail.pl",
};

async function fillControls(page: Page, root: Locator, message: string): Promise<number> {
  const controls = root.locator(
    "xpath=descendant-or-self::*[self::input or self::select or self::textarea]",
  );
  let filled = 0;
  for (let i = 0; i < (await controls.count()); i++) {
    const el = controls.nth(i);
    const tag = await el.evaluate((n) => n.tagName.toLowerCase());
    const type = (await el.getAttribute("type")) ?? "";
    const role = await el.getAttribute("role");
    if (tag === "select") {
      await el.selectOption({ index: 1 });
    } else if (type === "file") {
      await el.setInputFiles({
        name: "zalacznik.pdf",
        mimeType: "application/pdf",
        buffer: Buffer.from("%PDF-1.4\n%%EOF\n"),
      });
    } else if (type === "checkbox") {
      await el.check({ force: true });
    } else if (type === "radio") {
      if (await root.locator("input[type=radio]:checked").count()) continue;
      await el.check({ force: true });
    } else if (role === "combobox") {
      await el.click();
      const option = page.locator('[role="listbox"] [role="option"]').first();
      if (!(await option.isVisible())) await el.press("ArrowDown");
      await option.click({ timeout: 15_000 });
    } else if (type === "date") {
      await el.fill(SAMPLE.date);
    } else {
      const mode = await el.getAttribute("inputmode");
      const value = /PESEL/.test(message)
        ? SAMPLE.pesel
        : /NIP/.test(message)
          ? SAMPLE.nip
          : /REGON/.test(message)
            ? SAMPLE.regon
            : /kod pocztowy/.test(message)
              ? SAMPLE.zip
              : /e-mail/.test(message)
                ? SAMPLE.email
                : mode === "decimal"
                  ? SAMPLE.number
                  : SAMPLE.text;
      await el.fill(value);
    }
    filled++;
  }
  return filled;
}

/** Fills every field named in the error summary; returns how many controls it touched. */
async function fillFromErrorSummary(page: Page, scope: Locator): Promise<number> {
  const links = scope.locator('[role="alert"][aria-labelledby="error-summary-title"] a');
  let filled = 0;
  for (let i = 0; i < (await links.count()); i++) {
    const link = links.nth(i);
    const id = ((await link.getAttribute("href")) ?? "#").slice(1);
    // "label: message"; only the message says which validator failed.
    const message = (await link.innerText()).split(": ").at(-1) ?? "";
    const cell = scope.locator(`[data-cell="${id}"]`);
    const root = (await cell.count()) > 0 ? cell.first() : scope.locator(`[id="${id}"]`).first();
    filled += await fillControls(page, root, message);
  }
  return filled;
}

export interface WalkResult {
  steps: number;
  titles: string[];
  /** null when the walk reached the FINISH page. */
  blockedAt: string | null;
}

/**
 * Renders the e-form inside `scope`, clicks "Dalej" through every step to the FINISH summary.
 * Required fields block "Dalej", so a failed attempt fills what the error summary names.
 */
export async function walkForm(page: Page, scope: Locator): Promise<WalkResult> {
  const stepOf = async () => {
    const t = await scope.locator('nav[aria-label="Kroki formularza"] p').first().innerText();
    const m = /Krok (\d+) z (\d+)/.exec(t);
    return { n: Number(m?.[1]), total: Number(m?.[2]) };
  };
  const titles: string[] = [];
  let { n, total } = await stepOf();
  for (let guard = 0; guard < 80; guard++) {
    const h1 = scope.locator("h1").first();
    await expect(h1).toBeVisible();
    titles.push((await h1.innerText()).trim());
    if (n >= total) break;
    let advanced = false;
    for (let round = 0; round < 8 && !advanced; round++) {
      await scope.getByRole("button", { name: /^Dalej/ }).click();
      await expect
        .poll(
          async () =>
            (await stepOf()).n !== n || (await scope.locator("#error-summary-title").count()) > 0,
          { timeout: 10_000 },
        )
        .toBe(true);
      const now = await stepOf();
      if (now.n !== n) {
        advanced = true;
        ({ n, total } = now);
      } else if ((await fillFromErrorSummary(page, scope)) === 0) break;
    }
    if (!advanced) {
      const why = await scope
        .locator('[role="alert"][aria-labelledby="error-summary-title"] li')
        .allInnerTexts();
      return {
        steps: titles.length,
        titles,
        blockedAt: `${titles.at(-1) ?? "?"} [${why.join(" / ")}]`,
      };
    }
  }
  expect(n, "walk must end on the last step").toBe(total);
  // FINISH page: summary headings and the submit button, which only shows a notice.
  await expect(scope.getByRole("button", { name: "Wyślij wniosek" })).toBeVisible();
  await scope.getByRole("button", { name: "Wyślij wniosek" }).click();
  await expect(scope.getByRole("status")).toContainText("podgląd formularza");
  return { steps: titles.length, titles, blockedAt: null };
}
