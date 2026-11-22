import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import type { FormConfig } from "../form/types";
import { FormRenderer } from "./FormRenderer";

afterEach(cleanup);

const consent = (required: boolean, selectAllEnabled = false): FormConfig => ({
  title: "Zgody",
  flow: { links: [{ id: "l", source: "a", target: "b" }] },
  tabs: [
    {
      id: "a",
      title: "Oświadczenia",
      type: "MAIN",
      questions: [
        {
          x: 0,
          y: 0,
          rows: 1,
          cols: 3,
          field: {
            id: "s",
            type: "SECTION",
            techName: "sekcja",
            title: "Sekcja",
            repeatingSectionGrid: [
              {
                x: 0,
                y: 0,
                rows: 1,
                cols: 3,
                field: {
                  id: "c",
                  type: "CONSENT_SECTION",
                  techName: "zgody",
                  title: "",
                  consentSectionConfig: {
                    selectAllEnabled,
                    consents: [
                      { description: "<p>Zgoda A</p>", required },
                      { description: "<p>Zgoda B</p>", required },
                    ],
                  },
                },
              },
            ],
          },
        },
      ],
    },
    { id: "b", title: "Koniec", type: "FINISH", questions: [] },
  ],
});

describe("consents", () => {
  it("a required consent does not block Dalej in the preview", async () => {
    const user = userEvent.setup();
    render(<FormRenderer config={consent(true)} />);
    await user.click(screen.getByRole("button", { name: "Dalej" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Koniec" })).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("selectAllEnabled adds a button that ticks every consent", async () => {
    const user = userEvent.setup();
    render(<FormRenderer config={consent(true, true)} />);
    await user.click(screen.getByRole("button", { name: "Zaznacz wszystkie" }));
    const boxes = screen.getAllByRole("checkbox").slice(1) as HTMLInputElement[];
    expect(boxes.map((b) => b.checked)).toEqual([true, true]);
    expect(screen.getByRole("button", { name: "Odznacz wszystkie" })).toBeTruthy();
  });

  it("no select-all button unless enabled", () => {
    render(<FormRenderer config={consent(false)} />);
    expect(screen.queryByRole("button", { name: "Zaznacz wszystkie" })).toBeNull();
  });
});
