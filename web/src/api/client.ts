import { parseRetryAfter, TIMEOUT_MESSAGE } from "./retry";
import type { AnalysisResult } from "./types";

interface Problem {
  detail?: unknown;
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

/** Detail text from the API is shown only when it is a short plain sentence, never a dump. */
function readable(detail: unknown): string {
  if (typeof detail !== "string") return "";
  const text = detail.trim();
  if (!text || text.length > 300 || /traceback|^[{[<]/i.test(text)) return "";
  return /[.!?]$/.test(text) ? text : `${text}.`;
}

/** Polish message with a next step for an API status; `detail` is the problem+json detail. */
export function describeFailure(status: number, detail?: unknown): string {
  const api = readable(detail);
  if (status === 0) {
    return "Usługa jest niedostępna. Sprawdź, czy działa cały zestaw (docker compose up), i spróbuj ponownie.";
  }
  if (status === 400) {
    return `${api || "Nazwa pliku jest nieprawidłowa albo plik jest uszkodzony."} Zmień nazwę pliku lub wgraj go ponownie.`;
  }
  if (status === 401) {
    return "Usługa wymaga logowania albo token jest nieprawidłowy. Wpisz poprawny token w polu „Uwierzytelnianie” i użyj „Spróbuj ponownie”.";
  }
  if (status === 413) {
    return `${api || "Plik jest za duży."} Wgraj mniejszy plik, na przykład kilka stron osobno.`;
  }
  if (status === 415) {
    return `${api || "Typ pliku nie jest obsługiwany albo treść nie zgadza się z rozszerzeniem."} Wgraj PDF, DOC, DOCX, ODS, XLSX, JPG, JPEG lub PNG.`;
  }
  if (status === 422) {
    return "Nie udało się odczytać dokumentu. Wgraj wyraźniejszy skan albo ten sam blankiet w innym formacie, na przykład PDF z tekstem.";
  }
  if (status === 429) {
    return "Usługa przyjmuje ograniczoną liczbę plików na minutę. Odczekaj chwilę i spróbuj ponownie.";
  }
  if (status === 504) return TIMEOUT_MESSAGE;
  if (status >= 500) {
    return "Usługa jest niedostępna albo napotkała błąd. Sprawdź, czy działa cały zestaw, i spróbuj ponownie za chwilę.";
  }
  return `${api || `Usługa zwróciła błąd ${status}.`} Spróbuj ponownie.`;
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
    throw new ApiError(describeFailure(0), 0);
  }
  if (!response.ok) {
    const problem = (await response.json().catch(() => ({}))) as Problem | null;
    throw new ApiError(
      describeFailure(response.status, problem?.detail),
      response.status,
      response.status === 429 ? parseRetryAfter(response.headers.get("Retry-After")) : undefined,
    );
  }
  return (await response.json()) as AnalysisResult;
}
