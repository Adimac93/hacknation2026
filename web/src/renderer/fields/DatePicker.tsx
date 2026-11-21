import styles from "./Field.module.css";
import { FieldFrame } from "./frame";
import type { FieldProps } from "./types";

export function DatePicker(props: FieldProps) {
  const { id, value, onChange, readOnly, error } = props;
  return (
    <FieldFrame {...props}>
      {(describedBy) => (
        <input
          id={id}
          type="date"
          className={styles.control}
          value={value as string}
          onChange={(e) => onChange(e.target.value)}
          readOnly={readOnly}
          aria-describedby={describedBy}
          aria-invalid={error ? true : undefined}
        />
      )}
    </FieldFrame>
  );
}
