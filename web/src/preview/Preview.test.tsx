import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { Preview } from "./Preview";

afterEach(cleanup);

const pick = () => screen.getByLabelText("Wczytaj plik JSON") as HTMLInputElement;

describe("/podglad", () => {
  it("explains why a file is not a form configuration", async () => {
    const user = userEvent.setup();
    render(<Preview />);
    await user.upload(pick(), new File(["{ nie json"], "zly.json", { type: "application/json" }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/nie jest poprawnym JSON-em/);

    await user.upload(pick(), new File(['{"title": "x"}'], "inny.json"));
    expect((await screen.findByRole("alert")).textContent).toMatch(/Brak listy stron „tabs”/);
  });

  it("renders an uploaded configuration", async () => {
    const user = userEvent.setup();
    const text = readFileSync(resolve(process.cwd(), "public/examples/przyklad-1.json"), "utf8");
    render(<Preview />);
    await user.upload(pick(), new File([text], "wniosek.json", { type: "application/json" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Dane" })).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
