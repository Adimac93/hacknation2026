import { parseRetryAfter, TIMEOUT_MESSAGE } from "./retry";
import type { AnalysisResult } from "./types";

interface Problem {
  title?: string;
  detail?: string;
}

/** HTTP failure from the API; `retryAfter` is in seconds (only set for 429). */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly retryAfter?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Sends one file to the API and returns the form with its report. */
export async function analyzeFile(file: File, token?: string): Promise<AnalysisResult> {
  const body = new FormData();
  body.append("file", file);
  let response: Response;
  try {
    response = await fetch("/api/v1/forms?details=true", {
      method: "POST",
      body,
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
  } catch {
    throw new Error("Nie można połączyć się z usługą. Sprawdź, czy działa, i spróbuj ponownie.");
  }
  if (!response.ok) {
    const problem = (await response.json().catch(() => ({}))) as Problem;
    const message =
      response.status === 504
        ? TIMEOUT_MESSAGE
        : problem.detail || problem.title || `Usługa zwróciła błąd ${response.status}.`;
    throw new ApiError(
      message,
      response.status,
      response.status === 429 ? parseRetryAfter(response.headers.get("Retry-After")) : undefined,
    );
  }
  return (await response.json()) as AnalysisResult;
}
