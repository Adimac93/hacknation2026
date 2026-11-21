import type { AnalysisResult } from "./types";

interface Problem {
  title?: string;
  detail?: string;
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
    throw new Error(problem.detail || problem.title || `Usługa zwróciła błąd ${response.status}.`);
  }
  return (await response.json()) as AnalysisResult;
}
