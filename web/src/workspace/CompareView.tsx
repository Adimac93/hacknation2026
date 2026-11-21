import { useState } from "react";
import type { Report } from "../api/types";
import type { FormConfig } from "../form/types";
import { type FocusRequest, FormRenderer } from "../renderer/FormRenderer";
import { ReviewList } from "./ReviewList";
import { SourcePanel } from "./SourcePanel";
import styles from "./Workspace.module.css";

let seq = 0;

/** Document next to the form, with one selected field shared by list, select, lines and form. */
export function CompareView({ report, config }: { report: Report; config: FormConfig }) {
  const [focus, setFocus] = useState<FocusRequest | null>(null);

  const select = (techName: string | null) => {
    const origin = report.fields.find((f) => f.techName === techName);
    setFocus(
      techName && origin
        ? { techName, badge: `Źródło: ${origin.src.join(", ") || "brak"}`, seq: ++seq }
        : null,
    );
  };

  return (
    <>
      <ReviewList fields={report.fields} active={focus?.techName ?? null} onSelect={select} />
      <div className={styles.compare}>
        <SourcePanel report={report} active={focus?.techName ?? null} onSelect={select} />
        <div className={styles.preview}>
          <h2>Podgląd e-formularza</h2>
          <FormRenderer config={config} focusField={focus} />
        </div>
      </div>
    </>
  );
}
