import { validatorNames } from "../../form/validation";
import styles from "./Field.module.css";
import { FieldFrame } from "./frame";
import type { FieldProps } from "./types";

export function TextField(props: FieldProps) {
  const { field, id, value, onChange, readOnly, error } = props;
  const names = validatorNames(field.validation);
  const inputMode = names.includes("EMAIL")
    ? "email"
    : names.some((n) => ["PESEL", "NIP", "REGON", "ZIP_CODE"].includes(n))
      ? "numeric"
      : undefined;
  return (
    <FieldFrame {...props}>
      {(describedBy) => (
        <input
          id={id}
          type="text"
          className={styles.control}
          value={value as string}
          onChange={(e) => onChange(e.target.value)}
          readOnly={readOnly}
          inputMode={inputMode}
          placeholder={names.includes("ZIP_CODE") ? "00-000" : undefined}
          autoComplete="off"
          aria-describedby={describedBy}
          aria-invalid={error ? true : undefined}
        />
      )}
    </FieldFrame>
  );
}
