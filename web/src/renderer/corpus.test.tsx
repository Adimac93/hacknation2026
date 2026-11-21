// Walks every generated form (outputs/) and both organiser references (Docs/) through the
// renderer with seeded pseudo-random answers. Missing files fail loudly, nothing is skipped.

import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { compileConditions, evaluateConditions } from "../form/conditions";
import {
  fieldInstances,
  initialValue,
  isExternal,
  optionsOf,
  PRESENTATIONAL_TYPES,
} from "../form/model";
import { parseConfig } from "../form/parse";
import type { Answer, FormConfig } from "../form/types";
import { validatorNames } from "../form/validation";
import { FormRenderer } from "./FormRenderer";

afterEach(cleanup);

const ROOT = resolve(process.cwd(), "..");

function corpus(): { name: string; path: string }[] {
  const outputs = join(ROOT, "outputs");
  if (!existsSync(outputs)) throw new Error(`Brak katalogu ${outputs}`);
  const files = readdirSync(outputs)
    .filter((f) => f.endsWith(".json"))
    .map((f) => ({ name: `outputs/${f.slice(0, 12)}`, path: join(outputs, f) }));
  if (files.length < 6) throw new Error(`Oczekiwano 6 JSON-ów w outputs/, jest ${files.length}`);
  const docs = join(ROOT, "Docs");
  if (!existsSync(docs)) throw new Error(`Brak katalogu ${docs}`);
  for (const prefix of ["1. ", "5. "]) {
    const dir = readdirSync(docs).find((d) => d.startsWith(prefix));
    if (!dir) throw new Error(`Brak folderu Docs/"${prefix}*"`);
    const json = readdirSync(join(docs, dir)).find(
      (f) => f.startsWith("konfiguracja_") && f.endsWith(".json"),
    );
    if (!json) throw new Error(`Brak konfiguracja_*.json w Docs/${dir}`);
    files.push({ name: `Docs/${prefix}ref`, path: join(docs, dir, json) });
  }
  return files;
}

function rng(seed: number) {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const domId = (key: string) => `pole-${key.replace(/\W/g, "_")}`;

function weighted(ds: number[], weights: number[], mod: number): number {
  return weights.reduce((s, w, i) => s + w * (ds[i] ?? 0), 0) % mod;
}

/** A value that passes the named validators. */
function validText(names: string[], rand: () => number): string {
  const d = (n: number) => Array.from({ length: n }, () => Math.floor(rand() * 10));
  if (names.includes("PESEL")) {
    const ds = [...d(2), 0, 1, 1, 5, ...d(3)]; // month 01, day 15
    const check = (10 - weighted(ds, [1, 3, 7, 9, 1, 3, 7, 9, 1, 3], 10)) % 10;
    return [...ds.slice(0, 10), check].join("");
  }
  if (names.includes("NIP")) {
    for (;;) {
      const ds = d(9);
      const c = weighted(ds, [6, 5, 7, 2, 3, 4, 5, 6, 7], 11);
      if (c !== 10) return [...ds, c].join("");
    }
  }
  if (names.includes("REGON")) {
    const ds = d(8);
    return [...ds, weighted(ds, [8, 9, 2, 3, 4, 5, 6, 7], 11) % 10].join("");
  }
  if (names.includes("EMAIL")) return `jan${Math.floor(rand() * 1000)}@example.pl`;
  if (names.includes("ZIP_CODE")) return "90-001";
  if (names.includes("EPUAP")) return "/abc123/skrytka";
  if (names.includes("ADE")) return "AE:PL-12345-67890-ABCDE-12";
  return `Tekst ${Math.floor(rand() * 1000)}`;
}

function hasAccessibleName(el: Element): boolean {
  if (el.getAttribute("aria-label")?.trim()) return true;
  const by = el.getAttribute("aria-labelledby");
  if (by?.split(/\s+/).some((i) => document.getElementById(i)?.textContent?.trim())) return true;
  return Array.from((el as HTMLInputElement).labels ?? []).some((l) => l.textContent?.trim());
}

/** Same form with REQUIRED on every input field: the references never set any validator. */
function requireAll(config: FormConfig): FormConfig {
  const copy = structuredClone(config);
  for (const tab of copy.tabs) {
    for (const q of tab.questions) {
      for (const cell of q.field.repeatingSectionGrid) {
        if (!PRESENTATIONAL_TYPES.has(cell.field.type) && !isExternal(cell.field)) {
          cell.field.validation = ["REQUIRED", ...(cell.field.validation ?? [])];
        }
      }
    }
  }
  return copy;
}

const CASES = corpus().flatMap((c) => [
  { ...c, name: `${c.name} (as is)`, required: false },
  { ...c, name: `${c.name} (all REQUIRED)`, required: true },
]);

describe.each(CASES)("corpus $name", ({ path, required }) => {
  it("walks every step without errors", { timeout: 60_000 }, async () => {
    const parsed: FormConfig = parseConfig(readFileSync(path, "utf8"));
    const config = required ? requireAll(parsed) : parsed;
    const compiled = compileConditions(config);
    const rand = rng(20260101);
    const user = userEvent.setup({ delay: null });
    const consoleErrors: unknown[][] = [];
    const origError = console.error;
    console.error = (...args: unknown[]) => consoleErrors.push(args);
    try {
      render(<FormRenderer config={config} />);
      // Answers given by the test, by DOM id: the oracle for which fields must be hidden.
      const given = new Map<string, Answer>();
      // React reuses DOM nodes across steps, so both are reset per step.
      let filled = new WeakSet<Element>();
      let groups = new Set<string>();
      const stepCount = Number(
        /z (\d+)$/.exec(screen.getByText(/^Krok \d+ z \d+$/).textContent ?? "")?.[1],
      );
      expect(stepCount).toBeGreaterThanOrEqual(2);

      /** Field instance owning a control: DOM ids are `pole-…` or `pole-…-<n>` for options. */
      const ownerOf = (el: Element, t: number) => {
        const id = el.id;
        return fieldInstances(config, t, {}).find((i) => {
          const base = domId(i.key);
          return id === base || id.startsWith(`${base}-`);
        });
      };

      const fillPass = async (t: number) => {
        const form = document.querySelector("form") as HTMLFormElement;
        const controls = Array.from(
          form.querySelectorAll<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>(
            "input, select, textarea",
          ),
        );
        let changed = false;
        for (const el of controls) {
          if (filled.has(el) || (el as HTMLInputElement).readOnly || el.disabled) continue;
          const owner = ownerOf(el, t);
          const names = validatorNames(owner?.field.validation);
          const type = (el as HTMLInputElement).type;
          if (type === "radio") {
            const group = (el as HTMLInputElement).name;
            if (groups.has(group)) continue;
            groups.add(group);
            const radios = controls.filter((c) => (c as HTMLInputElement).name === group);
            const pick = radios[Math.floor(rand() * radios.length)] as HTMLInputElement;
            await user.click(pick);
            for (const r of radios) filled.add(r);
            if (owner) given.set(domId(owner.key), pick.value);
          } else if (type === "checkbox") {
            filled.add(el);
            // Consents are all accepted; plain checkboxes are picked at random.
            if (owner?.field.type === "CONSENT_SECTION" || rand() < 0.6) {
              await user.click(el);
              if (owner?.field.type === "CHECKBOX") {
                const id = optionsOf(owner.field)[Number(/-(\d+)$/.exec(el.id)?.[1] ?? 0)]?.id;
                const key = domId(owner.key);
                given.set(key, [...((given.get(key) as string[] | undefined) ?? []), id ?? ""]);
              }
            }
          } else if (type === "file") {
            filled.add(el);
            await user.upload(el, new File(["x"], "zalacznik.pdf", { type: "application/pdf" }));
          } else if (type === "date") {
            filled.add(el);
            fireEvent.change(el, { target: { value: "2024-05-14" } });
            if (owner) given.set(domId(owner.key), "2024-05-14");
          } else if (el.tagName === "SELECT") {
            filled.add(el);
            const opts = Array.from((el as HTMLSelectElement).options).filter((o) => o.value);
            const pick = opts[Math.floor(rand() * opts.length)];
            if (pick) {
              await user.selectOptions(el, pick.value);
              if (owner) given.set(domId(owner.key), pick.value);
            }
          } else if (el.getAttribute("role") === "combobox") {
            filled.add(el);
            await user.click(el);
            const opts = screen.queryAllByRole("option");
            const pick = opts[Math.floor(rand() * opts.length)];
            if (pick && owner) {
              const name = pick.textContent ?? "";
              await user.click(pick);
              given.set(
                domId(owner.key),
                optionsOf(owner.field).find((o) => o.name === name)?.id ?? name,
              );
            }
          } else {
            filled.add(el);
            const text =
              owner?.field.type === "NUMBER"
                ? String(Math.floor(rand() * 900) + 10)
                : validText(names, rand);
            await user.type(el, text);
            if (owner) given.set(domId(owner.key), text);
          }
          changed = true;
        }
        return changed;
      };

      for (let step = 0; step < stepCount; step++) {
        await screen.findByText(`Krok ${step + 1} z ${stepCount}`);
        filled = new WeakSet();
        groups = new Set();
        const h1 = screen.getAllByRole("heading", { level: 1 });
        expect(h1).toHaveLength(1);
        const t = config.tabs.findIndex((tab) => tab.title === h1[0]?.textContent);
        expect(
          t,
          `strona „${h1[0]?.textContent}” nie istnieje w konfiguracji`,
        ).toBeGreaterThanOrEqual(0);
        const last = step === stepCount - 1;

        // Settle conditions, then check hidden fields are absent and present ones rendered.
        const inspect = async () => {
          const conditions = await evaluateConditions(
            config,
            compiled,
            (field, key) => given.get(domId(key)) ?? initialValue(field, false),
            {},
          );
          await waitFor(() => {
            for (const inst of fieldInstances(config, t, {})) {
              const hidden =
                conditions.hidden.has(inst.sectionKey) || conditions.hidden.has(inst.template);
              const el = document.getElementById(domId(inst.key));
              if (hidden) expect(el, `ukryte pole w DOM: ${inst.field.title}`).toBeNull();
              else if (!PRESENTATIONAL_TYPES.has(inst.field.type))
                expect(el, `brak pola w DOM: ${inst.field.title}`).not.toBeNull();
            }
          });
        };

        const assertLabels = () => {
          const form = document.querySelector("form") as HTMLFormElement;
          for (const el of form.querySelectorAll("input, select, textarea")) {
            expect(hasAccessibleName(el), `brak etykiety: ${el.id || el.outerHTML}`).toBe(true);
          }
        };

        if (last) {
          expect(screen.getByRole("button", { name: "Wyślij wniosek" })).toBeTruthy();
          expect(screen.getAllByRole("button", { name: /^Zmień/ }).length).toBeGreaterThan(0);
          expect(screen.getAllByRole("term").length).toBeGreaterThan(0);
          assertLabels();
          await user.click(screen.getByRole("button", { name: "Wyślij wniosek" }));
          expect(await screen.findByRole("status")).toBeTruthy();
          break;
        }

        await inspect();
        assertLabels();
        // 1. Dalej on an untouched page: moves on, or explains why with links to real fields.
        await user.click(screen.getByRole("button", { name: "Dalej" }));
        const alert = screen.queryByRole("alert");
        if (!alert) {
          // Nothing blocked the empty page: go back and walk it again with answers.
          await screen.findByText(`Krok ${step + 2} z ${stepCount}`);
          await user.click(screen.getByRole("button", { name: "Wstecz" }));
          await screen.findByText(`Krok ${step + 1} z ${stepCount}`);
        }
        for (const a of alert?.querySelectorAll("a") ?? []) {
          const target = a.getAttribute("href")?.slice(1) ?? "";
          expect(
            document.getElementById(target),
            `błąd wskazuje na brak pola ${target}`,
          ).not.toBeNull();
        }
        expect(screen.getByText(`Krok ${step + 1} z ${stepCount}`)).toBeTruthy();
        if (required) expect(alert, "REQUIRED nie zablokowało Dalej").not.toBeNull();
        // 2. Fill until no new (conditional) controls show up, then go on.
        for (let pass = 0; pass < 6 && (await fillPass(t)); pass++) {
          await inspect(); // waits until the renderer has caught up with the answers
        }
        await inspect();
        assertLabels();
        await user.click(screen.getByRole("button", { name: "Dalej" }));
        const stuck = Array.from(screen.queryByRole("alert")?.querySelectorAll("li") ?? []).map(
          (li) => li.textContent,
        );
        expect(
          stuck,
          `krok ${step + 1} (${h1[0]?.textContent}) nie przechodzi po wypełnieniu`,
        ).toEqual([]);
      }
    } finally {
      console.error = origError;
    }
    expect(consoleErrors.map((a) => String(a[0]).slice(0, 200))).toEqual([]);
  });
});
