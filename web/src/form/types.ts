// Types of the COI form-generator configuration JSON, reconstructed from the two
// reference files in Docs/ (they, not the organiser's schema file, define the format).
// Optional markers follow what the reference files actually omit; the renderer must
// still tolerate missing keys because uploaded files can be anything.

export type TabType = "MAIN" | "FINISH";

export type ContainerType = "SECTION" | "REPEATING_SECTION";

export const FIELD_TYPES = [
  "TEXT_FIELD",
  "TEXTAREA",
  "NUMBER",
  "DATEPICKER",
  "SELECT",
  "RADIO",
  "CHECKBOX",
  "FILE_UPLOADER",
  "CONSENT_SECTION",
  "TEXT_BLOCK",
  "INFO_SECTION",
] as const;

export type FieldType = (typeof FIELD_TYPES)[number];

export const VALIDATOR_NAMES = [
  "REQUIRED",
  "EMAIL",
  "PESEL",
  "NIP",
  "REGON",
  "ZIP_CODE",
  "EPUAP",
  "ADE",
  "SERIAL_NUMBER_ID_CARD",
] as const;

export type ValidatorName = (typeof VALIDATOR_NAMES)[number];

export type StateType = "SHOW" | "READ_ONLY";

export interface FieldState {
  type: StateType | string;
  /** JSONata expression evaluated against the form with `__userAnswer` filled in. */
  query: string;
}

export interface FieldOption {
  id: string;
  name: string;
  techName?: string;
}

export interface Consent {
  /** HTML fragment. */
  description: string;
  required?: boolean;
}

export interface ConsentSectionConfig {
  consents: Consent[];
  files?: unknown[];
}

/**
 * Validation entries are empty in both references; the expected format is still an open
 * question to COI mentors. We accept plain names (`"REQUIRED"`) and objects carrying the
 * name under `type` or `name`.
 */
export type ValidationEntry = string | { type?: string; name?: string };

/** A single cell of a grid: a section on a page or a field in a section. */
export interface GridItem<F> {
  x: number;
  y: number;
  rows: number;
  cols: number;
  field: F;
}

interface BaseField {
  id: string;
  techName: string;
  title: string;
  /** HTML document string (`<html><head></head><body>…</body></html>`) or empty. */
  description?: string;
  options?: FieldOption[];
  validation?: ValidationEntry[];
  readOnly?: boolean;
  states?: FieldState[];
  questionOrder?: number;
  tooltipMessage?: string;
}

export interface FormField extends BaseField {
  type: FieldType | string;
  repeatingSectionGrid?: GridItem<FormField>[];
  /** String for text-like fields, list of option ids for SELECT. */
  defaultValue?: string | string[] | null;
  /** `"EXTERNAL_SYSTEM"` means `defaultValue` names a register attribute, e.g. `MLPZ.name`. */
  defaultValueType?: string | null;
  dictionaryName?: string;
  multiLevelTree?: boolean;
  searchEnabled?: boolean;
  consentSectionConfig?: ConsentSectionConfig;
}

export interface SectionField extends BaseField {
  type: ContainerType | string;
  /** Note: the organiser's schema file spells it `repetingSectionGrid`; references use this. */
  repeatingSectionGrid: GridItem<FormField>[];
}

export interface Tab {
  id: string;
  title: string;
  type: TabType | string;
  questions: GridItem<SectionField>[];
}

export interface FlowLink {
  id: string;
  source: string;
  target: string;
}

export interface FormConfig {
  title: string;
  tabs: Tab[];
  flow: { links: FlowLink[] };
}

export interface FileEntry {
  name: string;
  size: number;
}

/**
 * Value held for one field instance:
 * text-like fields and single choice: string; CHECKBOX: option ids;
 * CONSENT_SECTION: one flag per consent; FILE_UPLOADER: picked files.
 */
export type Answer = string | string[] | boolean[] | FileEntry[];
