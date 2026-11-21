import styles from "./Field.module.css";
import { FieldFrame } from "./frame";
import type { FieldProps } from "./types";

/** Text input with a decimal keyboard: native number inputs mishandle "1 250,50". */
export function NumberField(props: FieldProps) {
  const { id, value, onChange, readOnly, error } = props;
  return (
    <FieldFrame {...props}>
      {(describedBy) => (
        <input
          id={id}
          type="text"
          inputMode="decimal"
          className={styles.control}
          value={value as string}
          onChange={(e) => onChange(e.target.value)}
          readOnly={readOnly}
          autoComplete="off"
          aria-describedby={describedBy}
          aria-invalid={error ? true : undefined}
        />
      )}
    </FieldFrame>
  );
}
