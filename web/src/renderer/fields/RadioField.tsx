import { optionsOf } from "../../form/model";
import styles from "./Field.module.css";
import { ChoiceFrame } from "./frame";
import type { FieldProps } from "./types";

export function RadioField(props: FieldProps) {
  const { field, id, value, onChange, readOnly, error } = props;
  return (
    <ChoiceFrame {...props}>
      {() => (
        <div className={styles.options}>
          {optionsOf(field).map((option, i) => (
            <label key={option.id} className={styles.option}>
              <input
                type="radio"
                id={i === 0 ? id : `${id}-${i}`}
                name={id}
                value={option.id}
                checked={value === option.id}
                onChange={() => onChange(option.id)}
                disabled={readOnly}
                aria-invalid={error ? true : undefined}
              />
              {option.name}
            </label>
          ))}
        </div>
      )}
    </ChoiceFrame>
  );
}
