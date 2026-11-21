import { useState } from "react";
import { optionsOf } from "../../form/model";
import styles from "./Field.module.css";
import { FieldFrame } from "./frame";
import type { FieldProps } from "./types";

/** Lists longer than this get a filter box (COI standards: search above 15 options). */
export const FILTER_THRESHOLD = 15;

export function SelectField(props: FieldProps) {
  const { field, id, label, value, onChange, readOnly, error } = props;
  const [filter, setFilter] = useState("");
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

  const withFilter = options.length > FILTER_THRESHOLD;
  const needle = filter.trim().toLocaleLowerCase("pl");
  const shown = needle
    ? options.filter((o) => o.id === selected || o.name.toLocaleLowerCase("pl").includes(needle))
    : options;

  return (
    <FieldFrame {...props}>
      {(describedBy) => (
        <>
          {withFilter ? (
            <div className={styles.filter}>
              <input
                type="search"
                className={styles.control}
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="Wpisz, aby zawęzić listę"
                aria-label={`Filtruj listę: ${label}`}
                aria-controls={id}
                aria-describedby={`${id}-count`}
              />
              <p id={`${id}-count`} className={styles.status} aria-live="polite">
                {needle
                  ? `Pasujące pozycje: ${shown.length}`
                  : `Pozycji na liście: ${options.length}`}
              </p>
            </div>
          ) : null}
          <select
            id={id}
            className={styles.control}
            value={selected}
            onChange={(e) => onChange(e.target.value)}
            aria-describedby={describedBy}
            aria-invalid={error ? true : undefined}
          >
            <option value="">Wybierz</option>
            {shown.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </select>
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
