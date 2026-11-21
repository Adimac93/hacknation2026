import { optionsOf } from "../../form/model";
import styles from "./Field.module.css";
import { ChoiceFrame } from "./frame";
import type { FieldProps } from "./types";

export function CheckboxField(props: FieldProps) {
  const { field, id, value, onChange, readOnly, error } = props;
  const checked = value as string[];
  const toggle = (optionId: string) =>
    onChange(
      checked.includes(optionId) ? checked.filter((v) => v !== optionId) : [...checked, optionId],
    );
  return (
    <ChoiceFrame {...props}>
      {() => (
        <div className={styles.options}>
          {optionsOf(field).map((option, i) => (
            <label key={option.id} className={styles.option}>
              <input
                type="checkbox"
                id={i === 0 ? id : `${id}-${i}`}
                value={option.id}
                checked={checked.includes(option.id)}
                onChange={() => toggle(option.id)}
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
