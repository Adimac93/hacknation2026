import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SamplePicker } from "./SamplePicker";

const INDEX = {
  forms: [
    {
      form: "3",
      title: "Wniosek o wydanie zaświadczenia",
      reference: false,
      files: [
        { format: "PDF", path: "samples/3/w.pdf", name: "Wniosek.pdf", bytes: 4 },
        { format: "PNG", path: "samples/3/w.png", name: "Wniosek.png", bytes: 4 },
      ],
    },
  ],
};

function mockFetch() {
  const fetchMock = vi.fn(async (url: string) =>
    url === "/samples/index.json"
      ? new Response(JSON.stringify(INDEX))
      : new Response(new Blob(["%PDF"], { type: "application/pdf" })),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function open() {
  await userEvent.click(screen.getByText("Przykładowe blankiety z materiałów COI"));
}

describe("SamplePicker", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("fetches nothing until the list is opened", () => {
    const fetchMock = mockFetch();
    render(<SamplePicker onFiles={vi.fn()} />);

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("hands a picked sample over as a File with its original name", async () => {
    mockFetch();
    const onFiles = vi.fn();
    render(<SamplePicker onFiles={onFiles} />);

    await open();
    await userEvent.click(await screen.findByRole("button", { name: "PDF: Wniosek.pdf" }));

    await waitFor(() => expect(onFiles).toHaveBeenCalledTimes(1));
    const [files] = onFiles.mock.calls[0] as [File[]];
    expect(files.map((f) => f.name)).toEqual(["Wniosek.pdf"]);
  });

  it("sends every format of a form as one batch", async () => {
    mockFetch();
    const onFiles = vi.fn();
    render(<SamplePicker onFiles={onFiles} />);

    await open();
    await userEvent.click(await screen.findByRole("button", { name: "Wszystkie formaty" }));

    await waitFor(() => expect(onFiles).toHaveBeenCalledTimes(1));
    const [files] = onFiles.mock.calls[0] as [File[]];
    expect(files.map((f) => f.name)).toEqual(["Wniosek.pdf", "Wniosek.png"]);
  });

  it("says so when the sample index is missing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("", { status: 404 })),
    );
    render(<SamplePicker onFiles={vi.fn()} />);

    await open();

    expect(await screen.findByText("Lista przykładów jest niedostępna.")).toBeTruthy();
  });
});
