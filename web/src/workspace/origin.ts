import type { FieldOrigin } from "../api/types";

export const LOW_CONFIDENCE = 0.7;

/** Fields the clerk should check first: confidence below the threshold, lowest first. */
export function lowConfidence(fields: FieldOrigin[]): FieldOrigin[] {
  return fields
    .filter((f) => f.confidence < LOW_CONFIDENCE)
    .sort((a, b) => a.confidence - b.confidence);
}

/** Fields created from a document line. */
export function fieldsForLine(fields: FieldOrigin[], lineId: string): FieldOrigin[] {
  return fields.filter((f) => f.src.includes(lineId));
}

/** Next field to select when a line is clicked; repeated clicks cycle through its fields. */
export function pickForLine(
  fields: FieldOrigin[],
  lineId: string,
  current: string | null,
): string | null {
  const hits = fieldsForLine(fields, lineId);
  if (hits.length === 0) return null;
  const i = hits.findIndex((f) => f.techName === current);
  return (hits[(i + 1) % hits.length] as FieldOrigin).techName;
}
