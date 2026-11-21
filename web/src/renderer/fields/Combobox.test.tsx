import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";
import type { FieldOption } from "../../form/types";
import { Combobox } from "./Combobox";

const OPTIONS: FieldOption[] = ["Polska", "Portugalia", "Niemcy", "Francja"].map((n) => ({
  id: n,
  name: n,
}));

function Harness() {
  const [value, setValue] = useState("");
  return (
    <>
      <label htmlFor="k">Kraj</label>
      <Combobox id="k" options={OPTIONS} value={value} onChange={setValue} />
      <output>{value}</output>
    </>
  );
}

describe("Combobox", () => {
  afterEach(cleanup);

  it("narrows the list while typing in the same input and picks with Enter", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const box = screen.getByRole("combobox", { name: "Kraj" });

    await user.type(box, "po");
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual([
      "Polska",
      "Portugalia",
    ]);

    await user.keyboard("{ArrowDown}{Enter}");
    expect((box as HTMLInputElement).value).toBe("Portugalia");
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("picks an option with the mouse and shows an empty state", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const box = screen.getByRole("combobox", { name: "Kraj" });

    await user.type(box, "xyz");
    expect(screen.getByText("Brak pasujących pozycji")).toBeTruthy();

    await user.clear(box);
    await user.click(screen.getByRole("option", { name: "Niemcy" }));
    expect((box as HTMLInputElement).value).toBe("Niemcy");
  });
});
