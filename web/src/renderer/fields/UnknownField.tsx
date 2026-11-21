import styles from "./Field.module.css";
import type { FieldProps } from "./types";

/** Shown instead of crashing when a config uses a type outside the 11 COI components. */
export function UnknownField({ field }: FieldProps) {
  return (
    <div className={styles.unknown} role="note">
      Nieobsługiwany typ pola „{field.type || "brak typu"}”{field.title ? ` (${field.title})` : ""}.
      Podgląd go pomija.
    </div>
  );
}
