import { TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";
import { sanitizeHtml } from "../../form/html";
import { RichText } from "../RichText";
import styles from "./Field.module.css";
import type { FieldProps } from "./types";

type FrameProps = Pick<FieldProps, "field" | "id" | "label" | "error"> & {
  children: (describedBy: string | undefined) => ReactNode;
};

/** ids of the hint and error paragraphs that describe the control. */
export function describedBy(
  field: FieldProps["field"],
  id: string,
  error?: string,
): string | undefined {
  const ids = [
    sanitizeHtml(field.description) || field.tooltipMessage ? `${id}-hint` : "",
    error ? `${id}-error` : "",
  ].filter(Boolean);
  return ids.length > 0 ? ids.join(" ") : undefined;
}

function Hint({ field, id }: { field: FieldProps["field"]; id: string }) {
  if (!sanitizeHtml(field.description) && !field.tooltipMessage) return null;
  return (
    <div id={`${id}-hint`} className={styles.hint}>
      <RichText html={field.description} />
      {field.tooltipMessage ? <p>{field.tooltipMessage}</p> : null}
    </div>
  );
}

export function ErrorText({ id, error }: { id: string; error?: string }) {
  if (!error) return null;
  return (
    <p id={`${id}-error`} className={styles.error}>
      <TriangleAlert
        aria-hidden="true"
        size={20}
        strokeWidth={2}
        strokeLinecap="square"
        strokeLinejoin="miter"
      />
      <span className="visually-hidden">Błąd: </span>
      {error}
    </p>
  );
}

/** Label, hint and error around a single control. */
export function FieldFrame({ field, id, label, error, children }: FrameProps) {
  return (
    <div className={error ? `${styles.field} ${styles.invalid}` : styles.field}>
      <label htmlFor={id} className={styles.label}>
        {label}
      </label>
      <Hint field={field} id={id} />
      <ErrorText id={id} error={error} />
      {children(describedBy(field, id, error))}
    </div>
  );
}

/** fieldset and legend around a group of radios or checkboxes. */
export function ChoiceFrame({ field, id, label, error, children }: FrameProps) {
  const describe = describedBy(field, id, error);
  return (
    <fieldset
      className={
        error
          ? `${styles.field} ${styles.fieldset} ${styles.invalid}`
          : `${styles.field} ${styles.fieldset}`
      }
      aria-describedby={describe}
    >
      <legend className={label ? styles.label : "visually-hidden"}>{label || "Wybierz"}</legend>
      <Hint field={field} id={id} />
      <ErrorText id={id} error={error} />
      {children(describe)}
    </fieldset>
  );
}
