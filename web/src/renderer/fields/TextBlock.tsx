import { useLevel } from "../context";
import { RichText } from "../RichText";
import styles from "./Field.module.css";
import type { FieldProps } from "./types";

export function TextBlock({ field }: FieldProps) {
  const level = useLevel(3);
  return (
    <div className={styles.textBlock}>
      {field.title ? <h3 {...level}>{field.title}</h3> : null}
      <RichText html={field.description} />
    </div>
  );
}
