import { useEffect, useRef } from "react";
import { useLevel } from "./context";
import styles from "./FormRenderer.module.css";

export interface ErrorItem {
  id: string;
  label: string;
  message: string;
}

/** Error list shown after a failed "Dalej"; takes focus on every failed attempt. */
export function ErrorSummary({ items, attempt }: { items: ErrorItem[]; attempt: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const level = useLevel(2);
  // biome-ignore lint/correctness/useExhaustiveDependencies: refocus on each failed attempt.
  useEffect(() => {
    ref.current?.focus();
  }, [attempt]);

  return (
    <div
      ref={ref}
      className={styles.errorSummary}
      tabIndex={-1}
      role="alert"
      aria-labelledby="error-summary-title"
    >
      <h2 id="error-summary-title" {...level}>
        Popraw błędy w formularzu
      </h2>
      <ul>
        {items.map((item) => (
          <li key={item.id}>
            <a
              href={`#${item.id}`}
              onClick={(e) => {
                e.preventDefault();
                const target = document.getElementById(item.id);
                target?.focus();
                target?.scrollIntoView({ block: "center" });
              }}
            >
              {item.label ? `${item.label}: ` : ""}
              {item.message}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
