import { RichText } from "../RichText";
import styles from "./Field.module.css";
import type { FieldProps } from "./types";

export function InfoSection({ field }: FieldProps) {
  return (
    <div className={styles.info} role="note">
      {field.title ? <h3>{field.title}</h3> : null}
      <RichText html={field.description} />
    </div>
  );
}
