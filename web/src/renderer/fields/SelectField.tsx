import { optionsOf } from "../../form/model";
import { Combobox } from "./Combobox";
import styles from "./Field.module.css";
import { FieldFrame } from "./frame";
import type { FieldProps } from "./types";

/** Lists longer than this get search (COI standards: search above 15 options). */
export const FILTER_THRESHOLD = 15;

export function SelectField(props: FieldProps) {
  const { field, id, value, onChange, readOnly, error } = props;
  const options = optionsOf(field);
  const selected = value as string;

  if (readOnly) {
    const name = options.find((o) => o.id === selected)?.name ?? selected;
    return (
      <FieldFrame {...props}>
        {(describedBy) => (
          <input
            id={id}
            className={styles.control}
            value={name}
            readOnly
            aria-describedby={describedBy}
          />
        )}
      </FieldFrame>
    );
  }

  const searchable = options.length > FILTER_THRESHOLD || field.searchEnabled === true;

  return (
    <FieldFrame {...props}>
      {(describedBy) => (
        <>
          {searchable ? (
            <Combobox
              id={id}
              options={options}
              value={selected}
              onChange={onChange}
              describedBy={describedBy}
              invalid={Boolean(error)}
            />
          ) : (
            <select
              id={id}
              className={styles.control}
              value={selected}
              onChange={(e) => onChange(e.target.value)}
              aria-describedby={describedBy}
              aria-invalid={error ? true : undefined}
            >
              <option value="">Wybierz</option>
              {options.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </select>
          )}
          {options.length === 0 && field.dictionaryName ? (
            <p className={styles.status}>
              Słownik „{field.dictionaryName}” nie jest dostępny w podglądzie.
            </p>
          ) : null}
        </>
      )}
    </FieldFrame>
  );
}
