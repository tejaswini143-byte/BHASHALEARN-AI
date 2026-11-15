export type FileSelection = { name: string; type: string; size: number };
export const MAX_DOCUMENT_BYTES = 10 * 1024 * 1024;

export function validateDocumentSelection(file: FileSelection | undefined): string | null {
  if (!file) return null;
  const pdf = file.name.toLowerCase().endsWith(".pdf") && (!file.type || file.type === "application/pdf");
  const docx = file.name.toLowerCase().endsWith(".docx") && (!file.type || file.type === "application/vnd.openxmlformats-officedocument.wordprocessingml.document");
  if (!pdf && !docx) return "Choose a PDF or DOCX file.";
  if (file.size <= 0) return "The selected file is empty.";
  if (file.size > MAX_DOCUMENT_BYTES) return "Documents may be at most 10 MB.";
  return null;
}

export function createDocumentUploadBody(file: Blob & { name: string }): FormData {
  const body = new FormData();
  body.append("file", file, file.name);
  return body;
}
