import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, analyzeFile, describeFailure } from "./client";

const file = new File(["x"], "a.pdf", { type: "application/pdf" });

function problem(status: number, detail?: unknown, headers?: Record<string, string>) {
  return new Response(JSON.stringify({ title: "T", status, detail }), {
    status,
    headers: { "Content-Type": "application/problem+json", ...headers },
  });
}

async function failure(res: Response): Promise<ApiError> {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(res));
  return (await analyzeFile(file).catch((e: unknown) => e)) as ApiError;
}

afterEach(() => vi.unstubAllGlobals());

describe("describeFailure", () => {
  it("gives every status a Polish next step", () => {
    expect(describeFailure(400, "Nazwa zawiera znak ;.")).toMatch(
      /^Nazwa zawiera znak ;\. Zmień nazwę/,
    );
    expect(describeFailure(401)).toMatch(/Uwierzytelnianie/);
    expect(describeFailure(413, "Plik jest za duży (25 MB).")).toMatch(/Wgraj mniejszy/);
    expect(describeFailure(415)).toMatch(/PDF, DOC, DOCX/);
    expect(describeFailure(422)).toMatch(/skan/);
    expect(describeFailure(429)).toMatch(/Odczekaj/);
    expect(describeFailure(504)).toMatch(/zbyt długo/);
    expect(describeFailure(502)).toMatch(/Usługa jest niedostępna/);
    expect(describeFailure(0)).toMatch(/Usługa jest niedostępna/);
    expect(describeFailure(418)).toMatch(/błąd 418/);
  });

  it("never shows stack traces, JSON or long details", () => {
    for (const bad of ['{"a":1}', "Traceback (most recent call last): boom", "x".repeat(400), 42]) {
      expect(describeFailure(400, bad)).not.toMatch(/Traceback|\{|xxx|42/);
    }
  });

  it("ignores the API detail on statuses where it is not user-facing", () => {
    expect(describeFailure(500, "KeyError: 'x'")).not.toMatch(/KeyError/);
    expect(describeFailure(422, "internal")).not.toMatch(/internal/);
  });
});

describe("analyzeFile errors", () => {
  it("maps API problems to ApiError with status", async () => {
    const e = await failure(problem(415, "Zawartość nie zgadza się z rozszerzeniem."));
    expect(e).toBeInstanceOf(ApiError);
    expect(e.status).toBe(415);
    expect(e.message).toMatch(/^Zawartość nie zgadza się z rozszerzeniem\./);
  });

  it("copes with a non-JSON error body", async () => {
    const e = await failure(new Response("<html>bad gateway</html>", { status: 502 }));
    expect(e.status).toBe(502);
    expect(e.message).not.toMatch(/html/);
  });

  it("reads Retry-After only for 429", async () => {
    expect((await failure(problem(429, "x", { "Retry-After": "7" }))).retryAfter).toBe(7);
    expect((await failure(problem(500, "x", { "Retry-After": "7" }))).retryAfter).toBeUndefined();
  });

  it("reports a network failure as status 0", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const e = (await analyzeFile(file).catch((x: unknown) => x)) as ApiError;
    expect(e.status).toBe(0);
    expect(e.message).toMatch(/niedostępna/);
  });

  it("sends the bearer token when given", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await analyzeFile(file, "tok");
    expect(fetchMock.mock.calls[0]?.[1].headers).toEqual({ Authorization: "Bearer tok" });
  });
});
