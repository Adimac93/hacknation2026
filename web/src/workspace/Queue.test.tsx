import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { type Job, Queue } from "./Queue";
import { Upload } from "./Upload";

afterEach(cleanup);

const jobs: Job[] = [
  { id: 1, name: "a.pdf", size: 2048, status: "done" },
  {
    id: 2,
    name: "b.pdf",
    size: 2048,
    status: "error",
    error: "Coś poszło nie tak.",
    canRetry: true,
  },
  { id: 3, name: "c.pdf", size: 2048, status: "running" },
  { id: 4, name: "d.pdf", size: 2048, status: "waiting" },
  { id: 5, name: "e.pdf", size: 2048, status: "limited", retryAt: Date.now() + 30_000 },
];

function setup(list: Job[]) {
  const handlers = {
    onSelect: vi.fn(),
    onRemove: vi.fn(),
    onRetry: vi.fn(),
    onClearFinished: vi.fn(),
    onRemoveAll: vi.fn(),
  };
  render(<Queue jobs={list} selected={null} {...handlers} />);
  return handlers;
}

describe("Queue", () => {
  it("renders every status as text with a summary line", () => {
    setup(jobs);
    for (const label of ["Gotowe", "Błąd", "Analiza", "Czeka", "Czeka na limit"]) {
      expect(screen.getAllByText(label, { selector: "span" }).length).toBeGreaterThan(0);
    }
    expect(screen.getByText("Gotowe: 1, błędy: 1, w kolejce: 3")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toBe("Coś poszło nie tak.");
  });

  it("offers retry only for failed jobs that still hold their file", async () => {
    const h = setup([...jobs, { id: 6, name: "demo", size: 1, status: "error", error: "x" }]);
    const retry = screen.getAllByRole("button", { name: /Spróbuj ponownie/ });
    expect(retry).toHaveLength(1);
    await userEvent.click(retry[0] as HTMLElement);
    expect(h.onRetry).toHaveBeenCalledWith(2);
  });

  it("disables removal of a running job and removing all while one runs", () => {
    setup(jobs);
    expect(
      (screen.getByRole("button", { name: /Usuń c\.pdf/ }) as HTMLButtonElement).disabled,
    ).toBe(true);
    expect(
      (screen.getByRole("button", { name: "Usuń wszystkie" }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it("clears finished jobs and is disabled when none are finished", async () => {
    const h = setup(jobs);
    await userEvent.click(screen.getByRole("button", { name: "Wyczyść zakończone" }));
    expect(h.onClearFinished).toHaveBeenCalled();
    cleanup();
    setup([{ id: 1, name: "w.pdf", size: 1, status: "waiting" }]);
    expect(
      (screen.getByRole("button", { name: "Wyczyść zakończone" }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });
});

describe("Upload", () => {
  it("passes dropped and picked files on", async () => {
    const onFiles = vi.fn();
    const { container } = render(<Upload onFiles={onFiles} onDemo={() => {}} busy={false} />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const f = new File(["x"], "a.pdf");
    await userEvent.upload(input, f);
    expect(onFiles).toHaveBeenCalledWith([f]);
  });

  it("shows format and limit rules and the demo button", () => {
    render(<Upload onFiles={() => {}} onDemo={() => {}} busy={false} />);
    expect(screen.getByText(/PDF, DOC, DOCX/)).toBeTruthy();
    expect(screen.getByText("20 MB na plik")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Wczytaj dane przykładowe" })).toBeTruthy();
  });
});
