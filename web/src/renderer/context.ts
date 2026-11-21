import { createContext, useContext } from "react";
import type { Answer, FormField } from "../form/types";

/** What sections and fields need from the renderer, without prop drilling. */
export interface RendererApi {
  answerOf: (field: FormField, key: string) => Answer;
  setAnswer: (key: string, value: Answer) => void;
  isHidden: (key: string, template: string) => boolean;
  isReadOnly: (field: FormField, key: string) => boolean;
  errorOf: (key: string) => string | undefined;
  domId: (key: string) => string;
  rowsOf: (sectionKey: string) => number[];
  addRow: (sectionKey: string) => void;
  removeRow: (sectionKey: string, rowId: number) => void;
  /** Added to every heading level when the form is embedded below other headings. */
  headingOffset: number;
}

export const RendererContext = createContext<RendererApi | null>(null);

export function useRenderer(): RendererApi {
  const api = useContext(RendererContext);
  if (!api) throw new Error("useRenderer outside FormRenderer");
  return api;
}

/** aria-level override for a heading whose natural level is `base`; empty when standalone. */
export function useLevel(base: number): { "aria-level"?: number } {
  const { headingOffset } = useRenderer();
  return headingOffset > 0 ? { "aria-level": base + headingOffset } : {};
}
