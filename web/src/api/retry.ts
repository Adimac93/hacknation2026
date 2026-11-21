export const MAX_RETRIES = 5;
export const DEFAULT_RETRY_SECONDS = 60;
const MAX_RETRY_SECONDS = 300;

/** Parses a Retry-After header (delta-seconds or HTTP date); falls back to 60 s. */
export function parseRetryAfter(value: string | null | undefined, now = Date.now()): number {
  const raw = value?.trim();
  if (!raw) return DEFAULT_RETRY_SECONDS;
  const seconds = /^\d+$/.test(raw) ? Number(raw) : Math.ceil((Date.parse(raw) - now) / 1000);
  if (!Number.isFinite(seconds)) return DEFAULT_RETRY_SECONDS;
  return Math.min(Math.max(seconds, 1), MAX_RETRY_SECONDS);
}

/** Seconds to wait before retrying, or null when the failure is final. `attempt` = retries done. */
export function retryDelay(
  status: number | undefined,
  retryAfter: number | undefined,
  attempt: number,
): number | null {
  if (status !== 429 || attempt >= MAX_RETRIES) return null;
  return retryAfter ?? DEFAULT_RETRY_SECONDS;
}

export const TIMEOUT_MESSAGE =
  "Analiza trwała zbyt długo i usługa ją przerwała. Spróbuj ponownie lub wgraj mniejszy plik.";
