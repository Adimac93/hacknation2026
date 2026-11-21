import { describe, expect, it } from "vitest";
import { loadExample as load } from "../test/examples";
import { answerLookup, compileConditions, evaluateConditions } from "./conditions";
import { orderTabs, sectionKey, templateKey } from "./model";
import type { Answer, FormConfig } from "./types";

function locate(config: FormConfig, section: string, field?: string) {
  for (const [t, tab] of config.tabs.entries()) {
    for (const [q, item] of tab.questions.entries()) {
      if (item.field.techName !== section) continue;
      if (field === undefined) return sectionKey(t, q);
      const g = item.field.repeatingSectionGrid.findIndex((c) => c.field.techName === field);
      if (g >= 0) return templateKey(t, q, g);
    }
  }
  throw new Error(`not found: ${section}/${field}`);
}

describe("SHOW conditions on reference 5", () => {
  const config = load("przyklad-5.json");
  const compiled = compileConditions(config);
  const evaluate = (answers: Record<string, Answer>) =>
    evaluateConditions(config, compiled, answerLookup(answers), {});

  const who = locate(config, "podmiot_wniosku", "wybierz_w_czyim_imieniu_wnioskujesz");
  const role = locate(config, "podmiot_wniosku", "wybierz_jako_kto_wnioskujesz");
  const otherPerson = locate(config, "dane_innej_osoby");
  const entity = locate(config, "dane_podmiotu");
  const representative = locate(config, "potwierdzenie_ze_jestes_reprezentantem");

  it("compiles every query", () => {
    expect([...compiled.values()].flatMap((c) => c.errors)).toEqual([]);
  });

  it("hides dependent sections while nothing is chosen", async () => {
    const { hidden } = await evaluate({});
    expect(hidden.has(otherPerson)).toBe(true);
    expect(hidden.has(entity)).toBe(true);
    expect(hidden.has(role)).toBe(true);
  });

  it("'Innej osoby' shows the other person's data", async () => {
    const { hidden } = await evaluate({ [who]: "Innej osoby" });
    expect(hidden.has(otherPerson)).toBe(false);
    expect(hidden.has(entity)).toBe(true);
  });

  it("'Osoby prawnej…' shows entity data and the role question", async () => {
    const { hidden } = await evaluate({ [who]: "Osoby prawnej lub jednostki organizacyjnej" });
    expect(hidden.has(entity)).toBe(false);
    expect(hidden.has(role)).toBe(false);
    expect(hidden.has(otherPerson)).toBe(true);
    expect(hidden.has(representative)).toBe(true);
  });

  it("combines conditions with 'and'", async () => {
    const { hidden } = await evaluate({
      [who]: "Osoby prawnej lub jednostki organizacyjnej",
      [role]: "Reprezentant",
    });
    expect(hidden.has(representative)).toBe(false);
  });

  it("a hidden field's answer no longer counts", async () => {
    const { hidden } = await evaluate({ [who]: "Swoim", [role]: "Reprezentant" });
    expect(hidden.has(role)).toBe(true);
    expect(hidden.has(representative)).toBe(true);
  });

  it("'Polska' default shows Polish address fields and hides foreign ones", async () => {
    const { hidden } = await evaluate({});
    expect(hidden.has(locate(config, "adres_zamieszkania", "kod_pocztowy"))).toBe(false);
    expect(hidden.has(locate(config, "adres_zamieszkania", "kod_pocztowy_zagranica"))).toBe(true);
  });
});

describe("REPEATING_SECTION and READ_ONLY", () => {
  const config: FormConfig = {
    title: "Test",
    flow: { links: [] },
    tabs: [
      {
        id: "a",
        title: "Strona",
        type: "MAIN",
        questions: [
          {
            x: 0,
            y: 0,
            rows: 3,
            cols: 3,
            field: {
              id: "s",
              type: "REPEATING_SECTION",
              techName: "dzieci",
              title: "Dzieci",
              repeatingSectionGrid: [
                {
                  x: 0,
                  y: 0,
                  rows: 1,
                  cols: 3,
                  field: { id: "f1", type: "TEXT_FIELD", techName: "imie", title: "Imię" },
                },
                {
                  x: 0,
                  y: 1,
                  rows: 1,
                  cols: 3,
                  field: {
                    id: "f2",
                    type: "TEXT_FIELD",
                    techName: "uwagi",
                    title: "Uwagi",
                    states: [
                      {
                        type: "READ_ONLY",
                        query:
                          "\"Ala\" in tabs['Strona' in title].questions['dzieci' in field.techName].field.__userAnswer[$repeatingSectionIndex]['imie' in fieldTechName].answers",
                      },
                    ],
                  },
                },
              ],
            },
          },
        ],
      },
    ],
  };

  it("binds $repeatingSectionIndex per row", async () => {
    const compiled = compileConditions(config);
    const repeats = { "0.0": [0, 7] };
    const { readOnly } = await evaluateConditions(
      config,
      compiled,
      answerLookup({ "0.0#0.0": "Ola", "0.0#7.0": "Ala" }),
      repeats,
    );
    expect(readOnly.has("0.0#0.1")).toBe(false);
    expect(readOnly.has("0.0#7.1")).toBe(true);
  });
});

describe("orderTabs", () => {
  it("follows flow.links and ends with FINISH", () => {
    const config = load("przyklad-1.json");
    const order = orderTabs(config).map((i) => config.tabs[i]?.title);
    expect(order).toEqual(["Dane", "Informacje o budynku", "Kontakt z urzędem", "Strona końcowa"]);
  });
});
