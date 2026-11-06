import { expect, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

export const testEmail = process.env.BHASHALEARN_E2E_EMAIL || "";
export const testPassword = process.env.BHASHALEARN_E2E_PASSWORD || "";
export const secondTestEmail = process.env.BHASHALEARN_E2E_SECOND_EMAIL || "";
export const secondTestPassword = process.env.BHASHALEARN_E2E_SECOND_PASSWORD || "";
export const allowAuthenticatedTests = process.env.BHASHALEARN_E2E_ALLOW_AUTHENTICATED_READS === "1";
export const allowMutations = process.env.BHASHALEARN_E2E_ALLOW_MUTATIONS === "1";

export function requireDedicatedLogin() {
  return Boolean(allowAuthenticatedTests && testEmail && testPassword);
}

export function requireDocumentMutations() {
  return Boolean(allowMutations && requireDedicatedLogin());
}

export async function signIn(page: Page, email = testEmail, password = testPassword) {
  if (!email || !password) throw new Error("Dedicated E2E credentials were not configured.");
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel(/Password/).fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/dashboard(?:$|\?)/);
}

export async function openDocuments(page: Page) {
  await page.getByRole("link", { name: /documents/i }).first().click();
  await expect(page.getByRole("heading", { name: "Documents", exact: true })).toBeVisible();
}

export function makeTwoPagePdf(firstText: string, secondText: string): Buffer {
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 7 0 R >> >> /Contents 4 0 R >>",
    `<< /Length ${Buffer.byteLength(`BT /F1 18 Tf 72 720 Td (${pdfEscape(firstText)}) Tj ET`, "ascii")} >>\nstream\nBT /F1 18 Tf 72 720 Td (${pdfEscape(firstText)}) Tj ET\nendstream`,
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 7 0 R >> >> /Contents 6 0 R >>",
    `<< /Length ${Buffer.byteLength(`BT /F1 18 Tf 72 720 Td (${pdfEscape(secondText)}) Tj ET`, "ascii")} >>\nstream\nBT /F1 18 Tf 72 720 Td (${pdfEscape(secondText)}) Tj ET\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  let source = "%PDF-1.4\n";
  const offsets = [0];
  objects.forEach((object, index) => {
    offsets.push(Buffer.byteLength(source, "ascii"));
    source += `${index + 1} 0 obj\n${object}\nendobj\n`;
  });
  const xrefOffset = Buffer.byteLength(source, "ascii");
  source += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const offset of offsets.slice(1)) source += `${offset.toString().padStart(10, "0")} 00000 n \n`;
  source += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`;
  return Buffer.from(source, "ascii");
}

export function uniquePdfName(prefix = "bhashalearn-adv01-e2e") {
  return `${prefix}-${randomUUID()}.pdf`;
}

function pdfEscape(value: string) {
  return value.replaceAll("\\", "\\\\").replaceAll("(", "\\(").replaceAll(")", "\\)");
}
