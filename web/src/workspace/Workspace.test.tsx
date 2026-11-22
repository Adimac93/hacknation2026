import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Workspace } from "./Workspace";

const form: unknown = JSON.parse(
  readFileSync(resolve(process.cwd(), "public/examples/przyklad-5.json"), "utf8"),
);
const okBody = JSON.stringify({
  form,
  report: {
    mode: "rules",
    timings_ms: {},
    lint: [],
    fields: [],
    dictionary_proposals: [],
    document: { pages: [] },
  },
});

const ok = () => new Response(okBody, { status: 200 });
const fail = (status: number, detail?: string, headers?: Record<string, string>) =>
  new Response(JSON.stringify({ title: "T", detail }), { status, headers });

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  Element.prototype.scrollIntoView = () => {};
  render(<Workspace />);
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

/** Adds files through the hidden input and lets the queue's promises settle. */
async function upload(...files: File[]) {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  fireEvent.change(input, { target: { files } });
  await act(async () => {});
}
const pdf = (name = "a.pdf") => new File(["x"], name, { type: "application/pdf" });
const queue = () => within(screen.getByRole("region", { name: "Kolejka plików" }));

describe("Workspace upload validation", () => {
  it("rejects bad files with a reason and keeps the good ones", async () => {
    fetchMock.mockResolvedValue(ok());
    const big = new File(["x"], "big.pdf");
    Object.defineProperty(big, "size", { value: 21 * 1024 * 1024 });
    await upload(pdf("a;b.pdf"), pdf("a.txt"), new File([], "empty.pdf"), big, pdf("good.pdf"));
    const alert = screen.getByRole("alert", { name: "" });
    expect(alert.textContent).toContain("Nie dodano 4 plików");
    for (const part of [
      "niedozwolony znak",
      "nie jest obsługiwany",
      "pusty",
      "większy niż 20 MB",
    ]) {
      expect(alert.textContent).toContain(part);
    }
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("Workspace results", () => {
  it("selects the first finished result and keeps the chosen tab across files", async () => {
    fetchMock.mockImplementation(async () => ok());
    await upload(pdf("a.pdf"), pdf("b.pdf"));
    expect(screen.getByRole("heading", { name: "Wynik: a.pdf" })).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Raport" }));
    fireEvent.click(queue().getByRole("button", { name: "b.pdf" }));
    expect(screen.getByRole("heading", { name: "Wynik: b.pdf" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Raport" }).getAttribute("aria-selected")).toBe("true");
    expect(queue().getByText("Gotowe: 2, błędy: 0, w kolejce: 0")).toBeTruthy();
  });

  it("selects the next done job when the selected one is removed", async () => {
    fetchMock.mockImplementation(async () => ok());
    await upload(pdf("a.pdf"), pdf("b.pdf"));
    fireEvent.click(queue().getByRole("button", { name: /Usuń a\.pdf/ }));
    expect(screen.getByRole("heading", { name: "Wynik: b.pdf" })).toBeTruthy();
    fireEvent.click(queue().getByRole("button", { name: /Usuń b\.pdf/ }));
    expect(screen.queryByRole("heading", { name: /Wynik/ })).toBeNull();
  });

  it("does not steal focus when a result arrives", async () => {
    fetchMock.mockResolvedValue(ok());
    const input = document.querySelector("#jwt") as HTMLInputElement;
    input.focus();
    await upload(pdf());
    expect(document.activeElement).toBe(input);
  });

  it("clears finished jobs and removes all", async () => {
    fetchMock.mockResolvedValueOnce(ok()).mockResolvedValueOnce(fail(415));
    await upload(pdf("a.pdf"), pdf("b.pdf"));
    fireEvent.click(queue().getByRole("button", { name: "Wyczyść zakończone" }));
    expect(screen.queryByRole("region", { name: "Kolejka plików" })).toBeNull();
    expect(screen.queryByRole("heading", { name: /Wynik/ })).toBeNull();
    await upload(pdf("c.pdf"));
    fetchMock.mockResolvedValue(ok());
    fireEvent.click(queue().getByRole("button", { name: "Usuń wszystkie" }));
    expect(screen.queryByRole("region", { name: "Kolejka plików" })).toBeNull();
  });
});

describe("Workspace errors", () => {
  const cases: [number, string | undefined, RegExp][] = [
    [400, "Nazwa pliku jest zła.", /Nazwa pliku jest zła\. Zmień nazwę/],
    [413, "Plik jest za duży.", /Wgraj mniejszy plik/],
    [415, "Zły typ.", /Zły typ\. Wgraj PDF/],
    [422, "Dokument nieczytelny.", /wyraźniejszy skan/],
    [500, "KeyError", /Usługa jest niedostępna/],
    [503, undefined, /Usługa jest niedostępna/],
    [504, undefined, /zbyt długo/],
  ];
  it.each(cases)("shows a clear message for %i", async (status, detail, pattern) => {
    fetchMock.mockResolvedValue(fail(status, detail));
    await upload(pdf());
    expect(queue().getByRole("alert").textContent).toMatch(pattern);
    expect(queue().getByText("Błąd", { selector: "span" })).toBeTruthy();
  });

  it("shows a message when the network is down", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    await upload(pdf());
    expect(queue().getByRole("alert").textContent).toMatch(/Usługa jest niedostępna/);
  });

  it("opens the token field on 401 and retries with the token", async () => {
    fetchMock.mockResolvedValueOnce(fail(401, "Brak tokenu."));
    await upload(pdf());
    expect(queue().getByRole("alert").textContent).toMatch(/Uwierzytelnianie/);
    const details = screen.getByLabelText("Token JWT").closest("details") as HTMLDetailsElement;
    expect(details.open).toBe(true);

    fireEvent.change(screen.getByLabelText("Token JWT"), { target: { value: "tok" } });
    fetchMock.mockResolvedValueOnce(ok());
    fireEvent.click(queue().getByRole("button", { name: /Spróbuj ponownie/ }));
    await act(async () => {});
    expect(fetchMock.mock.calls[1]?.[1].headers).toEqual({ Authorization: "Bearer tok" });
    expect(screen.getByRole("heading", { name: "Wynik: a.pdf" })).toBeTruthy();
  });

  it("retries a failed file from memory and clears the error", async () => {
    fetchMock.mockResolvedValueOnce(fail(422)).mockResolvedValueOnce(ok());
    await upload(pdf());
    expect(queue().getByText("Gotowe: 0, błędy: 1, w kolejce: 0")).toBeTruthy();
    fireEvent.click(queue().getByRole("button", { name: /Spróbuj ponownie/ }));
    await act(async () => {});
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(queue().queryByRole("alert")).toBeNull();
    expect(queue().getByText("Gotowe: 1, błędy: 0, w kolejce: 0")).toBeTruthy();
  });

  it("removes a failed job and drops its file", async () => {
    fetchMock.mockResolvedValue(fail(415));
    await upload(pdf());
    fireEvent.click(queue().getByRole("button", { name: /Usuń a\.pdf/ }));
    expect(screen.queryByRole("region", { name: "Kolejka plików" })).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("Workspace rate limit", () => {
  it("waits for Retry-After on 429, then retries automatically", async () => {
    vi.useFakeTimers();
    fetchMock
      .mockResolvedValueOnce(fail(429, "Za dużo.", { "Retry-After": "5" }))
      .mockResolvedValueOnce(ok());
    await upload(pdf());
    expect(queue().getByText("Czeka na limit", { selector: "span" })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(() => vi.advanceTimersByTimeAsync(4000));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await act(() => vi.advanceTimersByTimeAsync(1500));
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("heading", { name: "Wynik: a.pdf" })).toBeTruthy();
  });

  it("shows elapsed seconds while a file is analysed", async () => {
    vi.useFakeTimers();
    fetchMock.mockReturnValue(new Promise(() => {}));
    await upload(pdf());
    await act(() => vi.advanceTimersByTimeAsync(3000));
    expect(queue().getByText(/Trwa to 3 s/)).toBeTruthy();
  });
});
