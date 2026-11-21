import { describe, expect, it } from "vitest";
import { MAX_RETRIES, parseRetryAfter, retryDelay } from "./retry";

describe("parseRetryAfter", () => {
  it("reads seconds", () => expect(parseRetryAfter("12")).toBe(12));
  it("falls back when missing or garbage", () => {
    expect(parseRetryAfter(null)).toBe(60);
    expect(parseRetryAfter("soon")).toBe(60);
  });
  it("reads an HTTP date", () => {
    const now = Date.parse("2026-01-01T00:00:00Z");
    expect(parseRetryAfter("Thu, 01 Jan 2026 00:00:30 GMT", now)).toBe(30);
  });
  it("clamps", () => {
    expect(parseRetryAfter("0")).toBe(1);
    expect(parseRetryAfter("99999")).toBe(300);
  });
});

describe("retryDelay", () => {
  it("retries only 429", () => {
    expect(retryDelay(429, 7, 0)).toBe(7);
    expect(retryDelay(504, 7, 0)).toBeNull();
    expect(retryDelay(undefined, undefined, 0)).toBeNull();
  });
  it("uses fallback and stops at the cap", () => {
    expect(retryDelay(429, undefined, 0)).toBe(60);
    expect(retryDelay(429, 7, MAX_RETRIES)).toBeNull();
  });
});
