import { RichText } from "../RichText";
import styles from "./Field.module.css";
import { ChoiceFrame } from "./frame";
import type { FieldProps } from "./types";

/** Consents and declarations; each consent's text is an HTML fragment. */
export function ConsentSection(props: FieldProps) {
  const { field, id, value, onChange, readOnly, error } = props;
  const flags = value as boolean[];
  const consents = field.consentSectionConfig?.consents ?? [];
  const toggle = (index: number) =>
    onChange(consents.map((_, i) => (i === index ? !flags[i] : Boolean(flags[i]))));
  return (
    <ChoiceFrame {...props} label={props.label || "Oświadczenia"}>
      {() => (
        <div className={styles.options}>
          {consents.map((consent, i) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: consents have no id; order is fixed.
            <label key={i} className={styles.option}>
              <input
                type="checkbox"
                id={i === 0 ? id : `${id}-${i}`}
                checked={Boolean(flags[i])}
                onChange={() => toggle(i)}
                disabled={readOnly}
                aria-invalid={error ? true : undefined}
                aria-required={consent.required ? true : undefined}
              />
              <RichText as="span" className={styles.consentText} html={consent.description} />
            </label>
          ))}
        </div>
      )}
    </ChoiceFrame>
  );
}
