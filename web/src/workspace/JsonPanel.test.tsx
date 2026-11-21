import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { JsonPanel } from "./JsonPanel";

afterEach(cleanup);

const form = {
  title: "Wniosek",
  tabs: [{ techName: "strona_1", type: "MAIN", fields: [{ techName: "imie" }] }],
  note: "x".repeat(120),
};

const items = () => screen.getAllByRole("treeitem");
const names = () => items().map((i) => i.textContent);

describe("JsonPanel tree", () => {
  it("shows the tree by default, two levels deep, with a switch to raw text", async () => {
    const user = userEvent.setup();
    render(<JsonPanel form={form} fileName="a.pdf" />);
    expect(screen.getByRole("tree")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Drzewo" }).getAttribute("aria-pressed")).toBe(
      "true",
    );
    const tabs = items().find((i) => i.textContent?.startsWith("▾tabs"));
    expect(tabs?.textContent).toContain("[1]");
    // level 3 container stays collapsed and its children are not rendered
    expect(items().some((i) => i.textContent?.includes("imie"))).toBe(false);
    await user.click(screen.getByRole("button", { name: "Tekst" }));
    expect(screen.queryByRole("tree")).toBeNull();
    expect(screen.getByLabelText("Treść pliku JSON").textContent).toContain('"techName"');
  });

  it("navigates with arrows, Home/End and toggles with Enter and Space", async () => {
    const user = userEvent.setup();
    render(<JsonPanel form={form} fileName="a.pdf" />);
    items()[0]?.focus();
    await user.keyboard("{ArrowDown}");
    expect(document.activeElement?.textContent).toContain("title");
    await user.keyboard("{End}");
    expect(document.activeElement?.textContent).toContain("note");
    await user.keyboard("{Home}");
    expect(document.activeElement?.textContent).toContain("{ 3 klucze }");
    // roving tabindex: exactly one tab stop
    expect(items().filter((i) => i.tabIndex === 0)).toHaveLength(1);

    await user.keyboard("{ArrowDown}{ArrowDown}"); // tabs
    expect(document.activeElement?.getAttribute("aria-expanded")).toBe("true");
    await user.keyboard("{ArrowLeft}");
    expect(document.activeElement?.getAttribute("aria-expanded")).toBe("false");
    await user.keyboard("{Enter}");
    expect(document.activeElement?.getAttribute("aria-expanded")).toBe("true");
    await user.keyboard("{ArrowRight}");
    expect(document.activeElement?.textContent).toContain("{ 3 klucze }");
    await user.keyboard("{ArrowLeft}");
    expect(document.activeElement?.textContent).toContain("tabs");
    await user.keyboard(" ");
    expect(document.activeElement?.getAttribute("aria-expanded")).toBe("false");
  });

  it("expands and collapses everything", async () => {
    const user = userEvent.setup();
    render(<JsonPanel form={form} fileName="a.pdf" />);
    await user.click(screen.getByRole("button", { name: "Rozwiń wszystko" }));
    expect(names().some((n) => n?.includes("imie"))).toBe(true);
    await user.click(screen.getByRole("button", { name: "Zwiń wszystko" }));
    expect(items()).toHaveLength(4); // root + its three children
  });

  it("truncates long strings and reveals them on demand", async () => {
    const user = userEvent.setup();
    render(<JsonPanel form={form} fileName="a.pdf" />);
    const note = items().find((i) => i.textContent?.includes("pokaż całość"));
    expect(note?.textContent).toContain("…");
    if (note) await user.click(note);
    expect(items().find((i) => i.textContent?.includes("zwiń"))?.textContent).toContain(
      "x".repeat(120),
    );
  });

  it("searches, announces the match count and opens the path to matches", async () => {
    const user = userEvent.setup();
    render(<JsonPanel form={form} fileName="a.pdf" />);
    await user.type(screen.getByLabelText("Szukaj w JSON"), "imie");
    expect(within(document.body).getByText("Dopasowań: 1.").getAttribute("aria-live")).toBe(
      "polite",
    );
    const hit = items().find((i) => i.dataset.match);
    expect(hit?.textContent).toContain("imie");
    expect(hit?.querySelector("mark")?.textContent).toBe("imie");
    await user.clear(screen.getByLabelText("Szukaj w JSON"));
    await user.type(screen.getByLabelText("Szukaj w JSON"), "zzz");
    expect(screen.getByText("Brak dopasowań.")).toBeTruthy();
  });

  it("marks important keys with a text tag", async () => {
    render(<JsonPanel form={form} fileName="a.pdf" />);
    await userEvent.click(screen.getByRole("button", { name: "Rozwiń wszystko" }));
    expect(screen.getAllByText("nazwa techniczna").length).toBe(2);
    expect(screen.getAllByText("typ").length).toBe(1);
  });
});
