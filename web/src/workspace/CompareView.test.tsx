import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import type { Report } from "../api/types";
import type { FormConfig, FormField } from "../form/types";
import { CompareView } from "./CompareView";

afterEach(cleanup);

const text = (techName: string, title: string): FormField => ({
  id: techName,
  type: "TEXT_FIELD",
  techName,
  title,
});

const page = (id: string, title: string, field: FormField) => ({
  id,
  title,
  type: "MAIN",
  questions: [
    {
      x: 0,
      y: 0,
      rows: 1,
      cols: 3,
      field: {
        id: `s-${id}`,
        type: "SECTION",
        techName: `sekcja_${id}`,
        title: `Sekcja ${title}`,
        repeatingSectionGrid: [{ x: 0, y: 0, rows: 1, cols: 3, field }],
      },
    },
  ],
});

const config = {
  title: "Test",
  flow: {
    links: [
      { id: "l1", source: "a", target: "b" },
      { id: "l2", source: "b", target: "end" },
    ],
  },
  tabs: [
    page("a", "Pierwsza", text("imie", "Imię")),
    page("b", "Druga", text("nazwisko", "Nazwisko")),
    { id: "end", title: "Koniec", type: "FINISH", questions: [] },
  ],
} as unknown as FormConfig;

const report: Report = {
  mode: "rules",
  timings_ms: {},
  lint: [],
  dictionary_proposals: [],
  fields: [
    { techName: "imie", src: ["L2"], confidence: 0.9 },
    { techName: "nazwisko", src: ["L3", "L4"], confidence: 0.5 },
  ],
  document: {
    pages: [
      {
        number: 1,
        lines: [
          { id: "L2", text: "Imię", kind: "TEXT" },
          { id: "L3", text: "Nazwisko", kind: "TEXT" },
          { id: "L4", text: "Nazwisko rodowe", kind: "TEXT" },
        ],
      },
    ],
  },
} as unknown as Report;

describe("CompareView", () => {
  it("lists low-confidence fields and jumps to the field on another step", async () => {
    const user = userEvent.setup();
    render(<CompareView report={report} config={config} />);
    expect(screen.getByRole("heading", { name: "Pola do sprawdzenia (1)" })).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /nazwisko/ }));

    const input = await screen.findByLabelText("Nazwisko");
    await waitFor(() => expect(document.activeElement).toBe(input));
    expect(screen.getByText("Źródło: L3, L4")).toBeTruthy();
    expect(screen.getAllByRole("button", { pressed: true }).length).toBeGreaterThan(0);
  });

  it("selects the field when its document line is clicked", async () => {
    const user = userEvent.setup();
    render(<CompareView report={report} config={config} />);
    await user.click(screen.getByRole("button", { name: /L2\s*Imię/ }));
    expect(await screen.findByText("Źródło: L2")).toBeTruthy();
    expect((screen.getByLabelText("Pokaż źródło pola") as HTMLSelectElement).value).toBe("imie");
  });
});
