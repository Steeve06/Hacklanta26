const MAX_BYTES = 10 * 1024 * 1024;
const ALLOWED = [".pdf", ".docx", ".zip"];

export function validateFile(file: File | null): string | undefined {
  if (!file) return undefined;
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!ALLOWED.includes(ext)) return "Upload a PDF, DOCX or ZIP file.";
  if (file.size > MAX_BYTES) return "Files must be 10 MB or smaller.";
  return undefined;
}
