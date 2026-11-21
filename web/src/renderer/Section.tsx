import { type CSSProperties, useEffect, useRef, useState } from "react";
import {
  byPosition,
  instanceKey,
  isRepeating,
  labelOf,
  sectionKey,
  templateKey,
} from "../form/model";
import type { FormField, GridItem, SectionField } from "../form/types";
import buttons from "./buttons.module.css";
import { useRenderer } from "./context";
import { componentFor } from "./fields";
import { RichText } from "./RichText";
import styles from "./Section.module.css";

/** grid-area from the config coordinates; a media query drops it below 640 px. */
export function gridArea(item: { x: number; y: number; rows: number; cols: number }) {
  return {
    "--area": `${item.y + 1} / ${item.x + 1} / span ${item.rows} / span ${item.cols}`,
  } as CSSProperties;
}

function FieldCell({
  cell,
  t,
  q,
  g,
  rowId,
}: {
  cell: GridItem<FormField>;
  t: number;
  q: number;
  g: number;
  rowId?: number;
}) {
  const api = useRenderer();
  const key = instanceKey(t, q, g, rowId);
  if (api.isHidden(key, templateKey(t, q, g))) return null;
  const field = cell.field;
  const Component = componentFor(field.type);
  // Only the first row of a repeating section is marked.
  const marked =
    api.marked?.template === templateKey(t, q, g) &&
    (rowId === undefined || rowId === api.rowsOf(sectionKey(t, q))[0]);
  return (
    <div
      className={styles.cell}
      style={gridArea(cell)}
      data-marked={marked || undefined}
      data-cell={api.domId(key)}
    >
      {marked ? <p className={styles.badge}>{api.marked?.badge}</p> : null}
      <Component
        field={field}
        id={api.domId(key)}
        label={labelOf(field)}
        value={api.answerOf(field, key)}
        onChange={(value) => api.setAnswer(key, value)}
        readOnly={api.isReadOnly(field, key)}
        error={api.errorOf(key)}
      />
    </div>
  );
}

function Grid({
  field,
  t,
  q,
  rowId,
}: {
  field: SectionField;
  t: number;
  q: number;
  rowId?: number;
}) {
  const cells = byPosition((field.repeatingSectionGrid ?? []).map((cell, g) => ({ ...cell, g })));
  return (
    <div className={styles.grid}>
      {cells.map((cell) => (
        <FieldCell key={cell.g} cell={cell} t={t} q={q} g={cell.g} rowId={rowId} />
      ))}
    </div>
  );
}

function RepeatingRows({ field, t, q }: { field: SectionField; t: number; q: number }) {
  const api = useRenderer();
  const sKey = sectionKey(t, q);
  const rows = api.rowsOf(sKey);
  const [focusRow, setFocusRow] = useState<number | null>(null);
  const headings = useRef(new Map<number, HTMLHeadingElement>());
  const addButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (focusRow === null) return;
    headings.current.get(focusRow)?.focus();
    setFocusRow(null);
  }, [focusRow]);

  const itemName = field.title || "Pozycja";
  return (
    <>
      {rows.map((rowId, index) => (
        <div key={rowId} className={styles.row}>
          <div className={styles.rowHeader}>
            <h3
              tabIndex={-1}
              className={styles.rowTitle}
              ref={(el) => {
                if (el) headings.current.set(rowId, el);
                else headings.current.delete(rowId);
              }}
            >
              {itemName} {index + 1}
            </h3>
            {rows.length > 1 ? (
              <button
                type="button"
                className={`${buttons.link} ${buttons.small}`}
                onClick={() => {
                  api.removeRow(sKey, rowId);
                  addButton.current?.focus();
                }}
              >
                Usuń
                <span className="visually-hidden">
                  : {itemName} {index + 1}
                </span>
              </button>
            ) : null}
          </div>
          <Grid field={field} t={t} q={q} rowId={rowId} />
        </div>
      ))}
      <button
        ref={addButton}
        type="button"
        className={buttons.secondary}
        onClick={() => {
          api.addRow(sKey);
          setFocusRow(Math.max(...rows) + 1);
        }}
      >
        Dodaj kolejną pozycję<span className="visually-hidden">: {itemName}</span>
      </button>
    </>
  );
}

export function Section({ item, t, q }: { item: GridItem<SectionField>; t: number; q: number }) {
  const api = useRenderer();
  const sKey = sectionKey(t, q);
  if (api.isHidden(sKey, sKey)) return null;
  const { field } = item;
  const known = field.type === "SECTION" || isRepeating(item);
  const headingId = `${api.domId(sKey)}-title`;

  return (
    <section
      className={styles.card}
      style={gridArea(item)}
      aria-labelledby={field.title ? headingId : undefined}
    >
      {field.title ? (
        <h2 id={headingId} className={styles.title}>
          {field.title}
        </h2>
      ) : null}
      <RichText html={field.description} className={styles.description} />
      {known ? null : (
        <p className={styles.warning} role="note">
          Element typu „{field.type || "brak typu"}” leży bezpośrednio na stronie. Pola muszą być w
          sekcji, więc podgląd pokazuje go jako sekcję.
        </p>
      )}
      {isRepeating(item) ? (
        <RepeatingRows field={field} t={t} q={q} />
      ) : (
        <Grid field={field} t={t} q={q} />
      )}
    </section>
  );
}
