import type { ComponentType } from "react";
import type { FieldType } from "../../form/types";
import { CheckboxField } from "./CheckboxField";
import { ConsentSection } from "./ConsentSection";
import { DatePicker } from "./DatePicker";
import { FileUploader } from "./FileUploader";
import { InfoSection } from "./InfoSection";
import { NumberField } from "./NumberField";
import { RadioField } from "./RadioField";
import { SelectField } from "./SelectField";
import { TextArea } from "./TextArea";
import { TextBlock } from "./TextBlock";
import { TextField } from "./TextField";
import type { FieldProps } from "./types";
import { UnknownField } from "./UnknownField";

export const FIELD_COMPONENTS: Record<FieldType, ComponentType<FieldProps>> = {
  TEXT_FIELD: TextField,
  TEXTAREA: TextArea,
  NUMBER: NumberField,
  DATEPICKER: DatePicker,
  SELECT: SelectField,
  RADIO: RadioField,
  CHECKBOX: CheckboxField,
  FILE_UPLOADER: FileUploader,
  CONSENT_SECTION: ConsentSection,
  TEXT_BLOCK: TextBlock,
  INFO_SECTION: InfoSection,
};

export function componentFor(type: string): ComponentType<FieldProps> {
  return FIELD_COMPONENTS[type as FieldType] ?? UnknownField;
}
