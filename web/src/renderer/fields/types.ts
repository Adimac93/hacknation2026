import type { Answer, FormField } from "../../form/types";

export interface FieldProps {
  field: FormField;
  /** DOM id of the (first) control; the error summary links to it. */
  id: string;
  label: string;
  value: Answer;
  onChange: (value: Answer) => void;
  readOnly: boolean;
  error?: string;
}
