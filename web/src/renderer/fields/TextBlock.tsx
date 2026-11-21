import { RichText } from "../RichText";
import styles from "./Field.module.css";
import type { FieldProps } from "./types";

export function TextBlock({ field }: FieldProps) {
  return (
    <div className={styles.textBlock}>
      {field.title ? <h3>{field.title}</h3> : null}
      <RichText html={field.description} />
    </div>
  );
}
