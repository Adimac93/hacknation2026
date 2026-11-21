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
  /** Template key and badge text of the field marked from outside (document review). */
  marked?: { template: string; badge: string };
  rowsOf: (sectionKey: string) => number[];
  addRow: (sectionKey: string) => void;
  removeRow: (sectionKey: string, rowId: number) => void;
}

export const RendererContext = createContext<RendererApi | null>(null);

export function useRenderer(): RendererApi {
  const api = useContext(RendererContext);
  if (!api) throw new Error("useRenderer outside FormRenderer");
  return api;
}
