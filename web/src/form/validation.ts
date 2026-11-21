// Page validation run on "Dalej". Pure: takes the field, its value and whether it is
// editable, returns a Polish message or null.

import { isEmptyAnswer, PRESENTATIONAL_TYPES, parseNumber } from "./model";
import type { Answer, FormField, ValidationEntry, ValidatorName } from "./types";
import { TEXT_VALIDATORS, VALIDATOR_MESSAGES } from "./validators";

/** Validator names from the `validation` list, whatever shape the entries take. */
export function validatorNames(entries: ValidationEntry[] | undefined): string[] {
  return (entries ?? [])
    .map((entry) => (typeof entry === "string" ? entry : (entry?.type ?? entry?.name ?? "")))
    .map((name) => name.trim().toUpperCase())
    .filter(Boolean);
}

export function validateField(
  field: FormField,
  value: Answer | undefined,
  readOnly: boolean,
): string | null {
  if (readOnly || PRESENTATIONAL_TYPES.has(field.type)) return null;
  const names = validatorNames(field.validation);

  if (field.type === "CONSENT_SECTION") {
    const flags = (value as boolean[] | undefined) ?? [];
    const consents = field.consentSectionConfig?.consents ?? [];
    const missing = consents.some((consent, i) => consent.required && !flags[i]);
    return missing || (names.includes("REQUIRED") && isEmptyAnswer(value))
      ? "Oświadczenie jest wymagane."
      : null;
  }

  if (isEmptyAnswer(value)) {
    return names.includes("REQUIRED") ? (VALIDATOR_MESSAGES.REQUIRED ?? null) : null;
  }
  if (typeof value !== "string") return null;

  if (field.type === "NUMBER" && parseNumber(value) === undefined) {
    return "Wpisz liczbę, np. 1250,50.";
  }
  for (const name of names) {
    const validate = TEXT_VALIDATORS[name as ValidatorName];
    if (validate && !validate(value.trim())) return VALIDATOR_MESSAGES[name] ?? null;
  }
  return null;
}
