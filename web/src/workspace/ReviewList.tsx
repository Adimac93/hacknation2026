import type { FieldOrigin } from "../api/types";
import { lowConfidence } from "./origin";
import styles from "./ReviewList.module.css";

interface Props {
  fields: FieldOrigin[];
  active: string | null;
  onSelect: (techName: string) => void;
}

/** Fields the model was unsure about; the clerk checks them against the document first. */
export function ReviewList({ fields, active, onSelect }: Props) {
  const items = lowConfidence(fields);
  return (
    <section aria-labelledby="review-title" className={styles.review}>
      <h2 id="review-title">Pola do sprawdzenia ({items.length})</h2>
      {items.length === 0 ? (
        <p>Brak pól o niskiej pewności.</p>
      ) : (
        <ul>
          {items.map((f) => (
            <li key={f.techName}>
              <button
                type="button"
                aria-pressed={f.techName === active}
                onClick={() => onSelect(f.techName)}
              >
                <span className="mono">{f.techName}</span>
                <span className={styles.percent}>{Math.round(f.confidence * 100)}%</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
