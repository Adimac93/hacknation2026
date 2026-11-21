import styles from "./Field.module.css";
import { FieldFrame } from "./frame";
import type { FieldProps } from "./types";

const MAX_LENGTH = 8000;

export function TextArea(props: FieldProps) {
  const { id, value, onChange, readOnly, error } = props;
  const text = value as string;
  return (
    <FieldFrame {...props}>
      {(describedBy) => (
        <>
          <textarea
            id={id}
            className={styles.control}
            value={text}
            onChange={(e) => onChange(e.target.value)}
            readOnly={readOnly}
            maxLength={MAX_LENGTH}
            rows={5}
            aria-describedby={[describedBy, `${id}-count`].filter(Boolean).join(" ")}
            aria-invalid={error ? true : undefined}
          />
          <p id={`${id}-count`} className={styles.counter}>
            <span className="visually-hidden">Liczba znaków: </span>
            {text.length}/{MAX_LENGTH}
          </p>
        </>
      )}
    </FieldFrame>
  );
}
