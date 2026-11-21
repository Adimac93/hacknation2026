// Client-side mirror of the upload rules (ARCHITECTURE.md, 9). The API stays authoritative.

export const ACCEPTED_EXTENSIONS = ["pdf", "doc", "docx", "ods", "xlsx", "jpg", "jpeg", "png"];
export const FORMAT_LABELS = ACCEPTED_EXTENSIONS.map((e) => e.toUpperCase()).join(", ");
export const MAX_UPLOAD_MB = 20;
const FORBIDDEN_NAME_CHARS = /[;:></\\|'*%$]/;

/** Returns a Polish message telling the user what to change, or null when the file is fine. */
export function validateUpload(
  file: { name: string; size: number },
  maxMb = MAX_UPLOAD_MB,
): string | null {
  const name = file.name.normalize("NFC");
  if (name.length > 250) return "Nazwa pliku ma więcej niż 250 znaków. Skróć ją.";
  if (FORBIDDEN_NAME_CHARS.test(name)) {
    return "Nazwa pliku zawiera niedozwolony znak (; : > < / \\ | ' * % $). Zmień nazwę.";
  }
  const ext = name.includes(".") ? name.split(".").pop()?.toLowerCase() : "";
  if (!ext || !ACCEPTED_EXTENSIONS.includes(ext)) {
    return `Ten typ pliku nie jest obsługiwany. Wybierz: ${FORMAT_LABELS}.`;
  }
  if (file.size === 0) return "Plik jest pusty.";
  if (file.size > maxMb * 1024 * 1024) return `Plik jest większy niż ${maxMb} MB.`;
  return null;
}

export function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1).replace(".", ",")} MB`;
}
