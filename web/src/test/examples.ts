import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { parseConfig } from "../form/parse";
import type { FormConfig } from "../form/types";

/** Loads a reference config copied to public/examples (tests run from web/). */
export function loadExample(name: string): FormConfig {
  return parseConfig(readFileSync(resolve(process.cwd(), "public/examples", name), "utf8"));
}
