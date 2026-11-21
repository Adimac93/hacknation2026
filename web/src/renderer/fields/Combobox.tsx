import { type KeyboardEvent, useEffect, useId, useMemo, useRef, useState } from "react";
import type { FieldOption } from "../../form/types";
import styles from "./Field.module.css";

interface Props {
  id: string;
  options: FieldOption[];
  value: string;
  onChange: (value: string) => void;
  describedBy?: string;
  invalid?: boolean;
}

/**
 * One text box that is also the list: typing narrows the options, arrows and Enter pick one
 * (ARIA 1.2 combobox with a listbox popup). Replaces a separate filter box plus a select.
 */
export function Combobox({ id, options, value, onChange, describedBy, invalid }: Props) {
  const listId = useId();
  const input = useRef<HTMLInputElement>(null);
  const selectedName = options.find((o) => o.id === value)?.name ?? "";
  const [query, setQuery] = useState<string | null>(null); // null: show the chosen name
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);

  const needle = (query ?? "").trim().toLocaleLowerCase("pl");
  const shown = useMemo(
    () =>
      needle ? options.filter((o) => o.name.toLocaleLowerCase("pl").includes(needle)) : options,
    [options, needle],
  );

  const close = () => {
    setOpen(false);
    setQuery(null);
  };

  const pick = (option: FieldOption) => {
    onChange(option.id);
    close();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    const last = shown.length - 1;
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setOpen(true);
        setActive((i) => Math.min(open ? i + 1 : i, last));
        break;
      case "ArrowUp":
        e.preventDefault();
        setActive((i) => Math.max(i - 1, 0));
        break;
      case "Home":
        if (open) {
          e.preventDefault();
          setActive(0);
        }
        break;
      case "End":
        if (open) {
          e.preventDefault();
          setActive(Math.max(last, 0));
        }
        break;
      case "Enter": {
        const option = shown[active];
        if (open && option) {
          e.preventDefault();
          pick(option);
        }
        break;
      }
      case "Escape":
        if (open) {
          e.preventDefault();
          close();
        } else if (value) {
          e.preventDefault();
          onChange("");
        }
        break;
      case "Tab":
        close();
        break;
    }
  };

  // Keep the highlighted option visible while moving with the arrow keys.
  useEffect(() => {
    if (open) document.getElementById(`${listId}-${active}`)?.scrollIntoView({ block: "nearest" });
  }, [open, active, listId]);

  const activeId = open && shown[active] ? `${listId}-${active}` : undefined;
  const count = needle
    ? `Pasujące pozycje: ${shown.length}`
    : `Pozycji na liście: ${options.length}`;

  return (
    <div className={styles.combobox}>
      <input
        ref={input}
        id={id}
        type="text"
        role="combobox"
        className={styles.control}
        autoComplete="off"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={activeId}
        aria-describedby={describedBy ? `${describedBy} ${id}-count` : `${id}-count`}
        aria-invalid={invalid ? true : undefined}
        placeholder="Wpisz, aby wyszukać, lub wybierz z listy"
        value={query ?? selectedName}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          setActive(0);
        }}
        onFocus={(e) => e.target.select()}
        onClick={() => setOpen(true)}
        onBlur={close}
        onKeyDown={onKeyDown}
      />
      <p id={`${id}-count`} className={styles.status} aria-live="polite">
        {open ? count : ""}
      </p>
      {open ? (
        <div id={listId} role="listbox" aria-label="Lista wyboru" className={styles.listbox}>
          {shown.length === 0 ? (
            <p className={styles.noMatch}>Brak pasujących pozycji</p>
          ) : (
            shown.map((option, i) => (
              <div
                key={option.id}
                id={`${listId}-${i}`}
                role="option"
                tabIndex={-1}
                aria-selected={option.id === value}
                data-active={i === active}
                className={styles.option2}
                // mousedown keeps the focus on the input, so blur does not close the list first.
                onMouseDown={(e) => {
                  e.preventDefault();
                  pick(option);
                }}
              >
                {option.name}
              </div>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
