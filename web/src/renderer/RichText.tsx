import { useMemo } from "react";
import { sanitizeHtml } from "../form/html";

interface Props {
  html: string | undefined;
  id?: string;
  className?: string;
  /** Use "span" inside labels, where block elements are not allowed. */
  as?: "div" | "span";
}

/** Renders a config HTML fragment after allow-list sanitising; nothing when it is empty. */
export function RichText({ html, id, className, as: Tag = "div" }: Props) {
  const clean = useMemo(() => sanitizeHtml(html), [html]);
  if (!clean) return null;
  // biome-ignore lint/security/noDangerouslySetInnerHtml: sanitised by sanitizeHtml (allow-list).
  return <Tag id={id} className={className} dangerouslySetInnerHTML={{ __html: clean }} />;
}
