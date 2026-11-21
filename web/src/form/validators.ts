// Pure validators for the COI validator names. Every validator treats an empty value as
// valid: emptiness is the job of REQUIRED. Test vectors live in fixtures/validators.json
// at the repository root and are shared with the backend.

import type { ValidatorName } from "./types";

const PESEL_WEIGHTS = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3];
const NIP_WEIGHTS = [6, 5, 7, 2, 3, 4, 5, 6, 7];
const REGON9_WEIGHTS = [8, 9, 2, 3, 4, 5, 6, 7];
const REGON14_WEIGHTS = [2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8];

function digits(value: string): number[] {
  return Array.from(value, Number);
}

function weightedSum(ds: number[], weights: number[]): number {
  return weights.reduce((sum, w, i) => sum + w * (ds[i] ?? 0), 0);
}

function isLeapYear(year: number): boolean {
  return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
}

function daysInMonth(year: number, month: number): number {
  if (month === 2) return isLeapYear(year) ? 29 : 28;
  return [4, 6, 9, 11].includes(month) ? 30 : 31;
}

/** PESEL: 11 digits, check digit and a real birth date (months encode the century). */
export function isValidPesel(value: string): boolean {
  if (value === "") return true;
  if (!/^\d{11}$/.test(value)) return false;
  const ds = digits(value);
  const check = (10 - (weightedSum(ds, PESEL_WEIGHTS) % 10)) % 10;
  if (check !== ds[10]) return false;

  const yy = Number(value.slice(0, 2));
  const mm = Number(value.slice(2, 4));
  const dd = Number(value.slice(4, 6));
  const century = [1900, 2000, 2100, 2200, 1800][Math.floor(mm / 20)];
  const month = mm % 20;
  if (century === undefined || month < 1 || month > 12) return false;
  return dd >= 1 && dd <= daysInMonth(century + yy, month);
}

/** NIP: 10 digits (dashes and spaces allowed), mod-11 check digit, remainder 10 is invalid. */
export function isValidNip(value: string): boolean {
  if (value === "") return true;
  const normalized = value.replace(/[-\s]/g, "");
  if (!/^\d{10}$/.test(normalized)) return false;
  const ds = digits(normalized);
  const check = weightedSum(ds, NIP_WEIGHTS) % 11;
  return check !== 10 && check === ds[9];
}

function regon9CheckOk(ds: number[]): boolean {
  return (weightedSum(ds, REGON9_WEIGHTS) % 11) % 10 === ds[8];
}

/** REGON: 9 or 14 digits; a 14-digit number must also start with a valid 9-digit REGON. */
export function isValidRegon(value: string): boolean {
  if (value === "") return true;
  if (/^\d{9}$/.test(value)) return regon9CheckOk(digits(value));
  if (/^\d{14}$/.test(value)) {
    const ds = digits(value);
    return regon9CheckOk(ds) && (weightedSum(ds, REGON14_WEIGHTS) % 11) % 10 === ds[13];
  }
  return false;
}

/** Polish postal code `00-000`. */
export function isValidZipCode(value: string): boolean {
  return value === "" || /^\d{2}-\d{3}$/.test(value);
}

// Pragmatic address check, portable to Python `re`: a dot-atom local part, at least two
// domain labels and a TLD of two or more letters.
const EMAIL_RE =
  /^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*@([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,}$/;

export function isValidEmail(value: string): boolean {
  return value === "" || EMAIL_RE.test(value);
}

export const TEXT_VALIDATORS: Partial<Record<ValidatorName, (value: string) => boolean>> = {
  EMAIL: isValidEmail,
  PESEL: isValidPesel,
  NIP: isValidNip,
  REGON: isValidRegon,
  ZIP_CODE: isValidZipCode,
};

export const VALIDATOR_MESSAGES: Record<string, string> = {
  REQUIRED: "To pole jest wymagane.",
  EMAIL: "Wpisz poprawny adres e-mail, np. jan.nowak@mail.pl.",
  PESEL: "Wpisz poprawny numer PESEL: 11 cyfr.",
  NIP: "Wpisz poprawny numer NIP: 10 cyfr.",
  REGON: "Wpisz poprawny numer REGON: 9 lub 14 cyfr.",
  ZIP_CODE: "Wpisz kod pocztowy w formacie 00-000.",
};
