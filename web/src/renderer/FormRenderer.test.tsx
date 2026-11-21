import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import type { FormConfig, FormField } from "../form/types";
import { loadExample } from "../test/examples";
import { FormRenderer } from "./FormRenderer";
import { FIELD_COMPONENTS } from "./fields";

afterEach(cleanup);

/** One MAIN page with the given fields in a single section, then a FINISH page. */
function formWith(fields: FormField[], sectionType = "SECTION"): FormConfig {
  return {
    title: "Formularz testowy",
    flow: { links: [{ id: "l", source: "main", target: "end" }] },
    tabs: [
      {
        id: "main",
        title: "Dane",
        type: "MAIN",
        questions: [
          {
            x: 0,
            y: 0,
            rows: fields.length,
            cols: 3,
            field: {
              id: "s",
              type: sectionType,
              techName: "sekcja",
              title: "Sekcja",
              repeatingSectionGrid: fields.map((field, y) => ({
                x: 0,
                y,
                rows: 1,
                cols: 3,
                field,
              })),
            },
          },
        ],
      },
      { id: "end", title: "Strona końcowa", type: "FINISH", questions: [] },
    ],
  };
}

describe.each(["przyklad-1.json", "przyklad-5.json"])("reference %s", (file) => {
  const config = loadExample(file);

  it("uses only supported field types", () => {
    const types = config.tabs.flatMap((tab) =>
      tab.questions.flatMap((q) => q.field.repeatingSectionGrid.map((c) => c.field.type)),
    );
    expect(types.filter((type) => !(type in FIELD_COMPONENTS))).toEqual([]);
  });

  it("renders every page without unsupported-type notes", async () => {
    const user = userEvent.setup();
    render(<FormRenderer config={config} />);
    const pages = config.tabs.length;
    for (let step = 1; step < pages; step++) {
      expect(screen.queryByText(/Nieobsługiwany typ/)).toBeNull();
      // Consents in the references are required.
      for (const box of screen.queryAllByRole("checkbox") as HTMLInputElement[]) {
        if (!box.checked) await user.click(box);
      }
      await user.click(screen.getByRole("button", { name: "Dalej" }));
      await screen.findByText(`Krok ${step + 1} z ${pages}`);
    }
    expect(screen.getByRole("heading", { level: 1, name: "Strona końcowa" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Wyślij wniosek" })).toBeTruthy();
    expect(screen.queryByText(/Nieobsługiwany typ/)).toBeNull();
  });
});

describe("SHOW conditions in reference 5", () => {
  it("choice in 'Podmiot wniosku' shows and hides dependent sections", async () => {
    const user = userEvent.setup();
    render(<FormRenderer config={loadExample("przyklad-5.json")} />);
    const subject = await screen.findByRole("region", { name: "Podmiot wniosku" });
    const otherPerson = () => screen.queryByRole("heading", { name: "Dane innej osoby" });
    const entity = () => screen.queryByRole("heading", { name: "Dane podmiotu" });

    await waitFor(() => expect(otherPerson()).toBeNull());
    expect(entity()).toBeNull();
    // The role question depends on choosing a legal entity.
    expect(within(subject).queryByRole("group", { name: "Wybierz, jako kto wnioskujesz" })).toBe(
      null,
    );

    await user.click(within(subject).getByRole("radio", { name: "Innej osoby" }));
    await waitFor(() => expect(otherPerson()).not.toBeNull());
    expect(entity()).toBeNull();

    await user.click(
      within(subject).getByRole("radio", { name: "Osoby prawnej lub jednostki organizacyjnej" }),
    );
    await waitFor(() => expect(entity()).not.toBeNull());
    expect(otherPerson()).toBeNull();
    expect(
      within(subject).getByRole("group", { name: "Wybierz, jako kto wnioskujesz" }),
    ).toBeTruthy();

    await user.click(within(subject).getByRole("radio", { name: "Swoim" }));
    await waitFor(() => expect(entity()).toBeNull());
    expect(otherPerson()).toBeNull();
  });

  it("register fields start empty and show sample data only on request", async () => {
    const user = userEvent.setup();
    render(<FormRenderer config={loadExample("przyklad-5.json")} />);
    const pesel = (await screen.findByLabelText("Numer PESEL")) as HTMLInputElement;
    expect(pesel.value).toBe("");

    await user.click(screen.getByLabelText("Pokaż przykładowe dane z rejestrów"));
    expect(pesel.readOnly).toBe(true);
    expect(pesel.value).toMatch(/^\d{11}$/);
  });
});

describe("validation on Dalej", () => {
  const pesel: FormField = {
    id: "p",
    type: "TEXT_FIELD",
    techName: "pesel",
    title: "PESEL",
    validation: ["REQUIRED", "PESEL"],
  };

  it("blocks the step, marks the field and focuses the summary", async () => {
    const user = userEvent.setup();
    render(<FormRenderer config={formWith([pesel])} />);
    await user.click(screen.getByRole("button", { name: "Dalej" }));

    const summary = await screen.findByRole("alert");
    expect(within(summary).getByText(/To pole jest wymagane/)).toBeTruthy();
    expect(document.activeElement).toBe(summary);
    const input = screen.getByLabelText("PESEL");
    expect(input.getAttribute("aria-invalid")).toBe("true");
    const describedBy = input.getAttribute("aria-describedby") ?? "";
    const error = document.getElementById(describedBy.split(" ").at(-1) ?? "");
    expect(error?.textContent).toMatch(/To pole jest wymagane/);

    await user.type(input, "12345678901");
    await user.click(screen.getByRole("button", { name: "Dalej" }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/PESEL/);

    await user.clear(input);
    await user.type(input, "44051401359");
    await user.click(screen.getByRole("button", { name: "Dalej" }));
    await screen.findByRole("heading", { level: 1, name: "Strona końcowa" });
    expect(screen.getByText("44051401359")).toBeTruthy();
  });

  it("'Wstecz' returns to the previous page with answers kept", async () => {
    const user = userEvent.setup();
    render(<FormRenderer config={formWith([{ ...pesel, validation: [] }])} />);
    await user.type(screen.getByLabelText("PESEL"), "abc");
    await user.click(screen.getByRole("button", { name: "Dalej" }));
    await user.click(await screen.findByRole("button", { name: "Wstecz" }));
    expect((screen.getByLabelText("PESEL") as HTMLInputElement).value).toBe("abc");
  });
});

describe("field behaviour", () => {
  it("REPEATING_SECTION adds and removes rows", async () => {
    const user = userEvent.setup();
    const child: FormField = { id: "c", type: "TEXT_FIELD", techName: "imie", title: "Imię" };
    render(<FormRenderer config={formWith([child], "REPEATING_SECTION")} />);
    expect(screen.getAllByLabelText("Imię")).toHaveLength(1);

    await user.click(screen.getByRole("button", { name: /Dodaj kolejną pozycję/ }));
    expect(screen.getAllByLabelText("Imię")).toHaveLength(2);
    await user.type(screen.getAllByLabelText("Imię")[1] as HTMLElement, "Ola");

    await user.click(screen.getByRole("button", { name: /Usuń.*Sekcja 1$/ }));
    const left = screen.getAllByLabelText("Imię") as HTMLInputElement[];
    expect(left.map((i) => i.value)).toEqual(["Ola"]);
    expect(screen.queryByRole("button", { name: /Usuń/ })).toBeNull();
  });

  it("long dictionary lists get a filter", async () => {
    const user = userEvent.setup();
    const country: FormField = {
      id: "k",
      type: "SELECT",
      techName: "kraj",
      title: "Kraj",
      dictionaryName: "Kraje",
    };
    render(<FormRenderer config={formWith([country])} />);
    const select = screen.getByLabelText("Kraj") as HTMLSelectElement;
    expect(select.options.length).toBeGreaterThan(16);
    await user.type(screen.getByRole("searchbox"), "niem");
    expect(Array.from(select.options, (o) => o.text)).toEqual(["Wybierz", "Niemcy"]);
  });

  it("unknown field types show a note instead of crashing", () => {
    const odd: FormField = { id: "x", type: "SIGNATURE", techName: "podpis", title: "Podpis" };
    render(<FormRenderer config={formWith([odd])} />);
    expect(screen.getByText(/Nieobsługiwany typ pola „SIGNATURE”/)).toBeTruthy();
  });

  it("'Przerwij wypełnianie' clears answers", async () => {
    const user = userEvent.setup();
    const name: FormField = { id: "n", type: "TEXT_FIELD", techName: "n", title: "Nazwa" };
    render(<FormRenderer config={formWith([name])} />);
    await user.type(screen.getByLabelText("Nazwa"), "abc");
    await user.click(screen.getByRole("button", { name: "Przerwij wypełnianie" }));
    expect((screen.getByLabelText("Nazwa") as HTMLInputElement).value).toBe("");
    expect(screen.getByRole("status").textContent).toMatch(/Przerwano/);
  });
});
