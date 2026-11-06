import { test, expect } from "@playwright/test";
import { allowAuthenticatedTests, allowMutations, makeTwoPagePdf, openDocuments, requireDocumentMutations, signIn, testEmail, testPassword, secondTestEmail, secondTestPassword, uniquePdfName } from "./helpers";

const validPdf = () => makeTwoPagePdf("BHASHALEARN ADV01 TEST PAGE ONE", "BHASHALEARN ADV01 TEST PAGE TWO");

test("documents route rejects unauthenticated visitors", async ({ page }) => {
  await page.goto("/documents");
  await expect(page).toHaveURL(/\/login$/);
});

test("student uploads, views extracted pages after refresh, and deletes only the new test PDF", async ({ page }) => {
  test.skip(!allowAuthenticatedTests || !requireDocumentMutations(), "Requires a dedicated E2E PostgreSQL database, isolated storage, and explicitly authorized test account.");
  await signIn(page, testEmail, testPassword);
  await openDocuments(page);
  const filename = uniquePdfName();
  const uploaded = page.waitForResponse(response => response.url().includes("/api/v1/documents") && response.request().method() === "POST");
  await page.getByLabel("Choose PDF file").setInputFiles({ name: filename, mimeType: "application/pdf", buffer: validPdf() });
  await page.getByRole("button", { name: "Upload PDF" }).click();
  const uploadResponse = await uploaded;
  expect(uploadResponse.status()).toBe(201);
  const uploadedDocument = await uploadResponse.json() as { id: string };
  const ownerToken = await page.evaluate(() => sessionStorage.getItem("bhashalearn_access_token"));
  await expect(page.getByRole("status")).toContainText(/uploaded and text extracted/i);
  const row = page.locator(".document-row").filter({ hasText: filename });
  await expect(row).toBeVisible();
  await row.getByRole("link", { name: "View" }).click();
  await expect(page.getByRole("heading", { name: filename })).toBeVisible();
  await expect(page.getByText("2 pages", { exact: true })).toBeVisible();
  await expect(page.getByText("BHASHALEARN ADV01 TEST PAGE ONE")).toBeVisible();
  await expect(page.getByText("BHASHALEARN ADV01 TEST PAGE TWO")).toBeVisible();
  await page.reload();
  await expect(page.getByText("BHASHALEARN ADV01 TEST PAGE ONE")).toBeVisible();
  await page.getByRole("link", { name: /all documents/i }).click();
  page.once("dialog", dialog => dialog.accept());
  const deletion = page.waitForResponse(response => response.url().includes("/api/v1/documents/") && response.request().method() === "DELETE");
  await page.locator(".document-row").filter({ hasText: filename }).getByRole("button", { name: "Delete" }).click();
  expect((await deletion).status()).toBe(204);
  await expect(page.getByText(filename)).toHaveCount(0);
  const deletedStatus = await page.evaluate(async ({ id, token }) => fetch(`/api/v1/documents/${id}`, { headers: { Authorization: `Bearer ${token}` } }).then(response => response.status), { id: uploadedDocument.id, token: ownerToken });
  expect(deletedStatus).toBe(404);
});

test("unsupported file and oversized file are rejected in the browser before upload", async ({ page }) => {
  test.skip(!allowAuthenticatedTests || !requireDocumentMutations(), "Requires an explicitly authorized disposable E2E account.");
  await signIn(page, testEmail, testPassword);
  await openDocuments(page);
  await page.getByLabel("Choose PDF file").setInputFiles({ name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("not pdf") });
  await expect(page.getByRole("alert")).toContainText("Choose a PDF file");
  const tooLarge = Buffer.alloc(10 * 1024 * 1024 + 1, 65);
  await page.getByLabel("Choose PDF file").setInputFiles({ name: "large.pdf", mimeType: "application/pdf", buffer: tooLarge });
  await expect(page.getByRole("alert")).toContainText("10 MB");
});

test("corrupt PDF is rejected and a textless PDF is clearly labeled", async ({ page }) => {
  test.skip(!allowAuthenticatedTests || !requireDocumentMutations(), "Requires an explicitly authorized disposable E2E account.");
  await signIn(page, testEmail, testPassword);
  await openDocuments(page);
  await page.getByLabel("Choose PDF file").setInputFiles({ name: "corrupt-e2e.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.7\ncorrupt body") });
  await page.getByRole("button", { name: "Upload PDF" }).click();
  await expect(page.getByRole("alert")).toContainText(/corrupted|invalid/i);
  await page.getByLabel("Choose PDF file").setInputFiles({ name: uniquePdfName("textless"), mimeType: "application/pdf", buffer: makeTwoPagePdf("", "") });
  await page.getByRole("button", { name: "Upload PDF" }).click();
  await expect(page.getByRole("status")).toContainText(/no selectable text|scanned PDF OCR is not supported/i);
  await expect(page.getByText("No selectable text", { exact: true })).toBeVisible();
  const textlessRow = page.locator(".document-row").filter({ hasText: "No selectable text" });
  page.once("dialog", dialog => dialog.accept());
  await textlessRow.getByRole("button", { name: "Delete" }).click();
  await expect(textlessRow).toHaveCount(0);
});

test("password-protected PDF is rejected when a disposable encrypted fixture is supplied", async ({ page }) => {
  const encryptedFixture = process.env.BHASHALEARN_E2E_ENCRYPTED_PDF;
  test.skip(!allowAuthenticatedTests || !requireDocumentMutations() || !encryptedFixture, "Set BHASHALEARN_E2E_ENCRYPTED_PDF to a non-sensitive password-protected test fixture and enable disposable test mutations.");
  await signIn(page, testEmail, testPassword);
  await openDocuments(page);
  await page.getByLabel("Choose PDF file").setInputFiles(encryptedFixture!);
  await page.getByRole("button", { name: "Upload PDF" }).click();
  await expect(page.getByRole("alert")).toContainText(/password-protected PDFs are not supported/i);
});

test("student document data stays isolated between two dedicated test accounts", async ({ browser }) => {
  test.skip(!allowMutations || !allowAuthenticatedTests || !testEmail || !testPassword || !secondTestEmail || !secondTestPassword, "Requires two dedicated test students and an explicitly configured disposable database.");
  const owner = await browser.newPage();
  const otherStudent = await browser.newPage();
  await signIn(owner, testEmail, testPassword);
  await openDocuments(owner);
  const filename = uniquePdfName("bhashalearn-adv01-isolation");
  await owner.getByLabel("Choose PDF file").setInputFiles({ name: filename, mimeType: "application/pdf", buffer: validPdf() });
  const uploadPromise = owner.waitForResponse(response => response.url().includes("/api/v1/documents") && response.request().method() === "POST");
  await owner.getByRole("button", { name: "Upload PDF" }).click();
  const uploadResponse = await uploadPromise;
  expect(uploadResponse.status()).toBe(201);
  const documentId = (await uploadResponse.json()).id as string;
  const ownerToken = await owner.evaluate(() => sessionStorage.getItem("bhashalearn_access_token"));
  await signIn(otherStudent, secondTestEmail, secondTestPassword);
  await openDocuments(otherStudent);
  await expect(otherStudent.getByText(filename)).toHaveCount(0);
  const secondToken = await otherStudent.evaluate(() => sessionStorage.getItem("bhashalearn_access_token"));
  const list = await otherStudent.evaluate(async token => {
    const response = await fetch("/api/v1/documents", { headers: { Authorization: `Bearer ${token}` } });
    return { status: response.status, body: await response.json() };
  }, secondToken);
  expect(list.status).toBe(200);
  expect(Array.isArray(list.body)).toBe(true);
  expect(list.body.some((item: { id: string }) => item.id === documentId)).toBe(false);
  for (const suffix of ["", "/pages"]) {
    const response = await otherStudent.evaluate(async ({ token, id, suffix }) => fetch(`/api/v1/documents/${id}${suffix}`, { headers: { Authorization: `Bearer ${token}` } }).then(result => result.status), { token: secondToken, id: documentId, suffix });
    expect(response).toBe(404);
  }
  const unauthorizedDelete = await otherStudent.evaluate(async ({ token, id }) => fetch(`/api/v1/documents/${id}`, { method: "DELETE", headers: { Authorization: `Bearer ${token}` } }).then(result => result.status), { token: secondToken, id: documentId });
  expect(unauthorizedDelete).toBe(404);
  const ownerCanStillRead = await owner.evaluate(async ({ token, id }) => fetch(`/api/v1/documents/${id}`, { headers: { Authorization: `Bearer ${token}` } }).then(response => response.status), { token: ownerToken, id: documentId });
  expect(ownerCanStillRead).toBe(200);
  pageDialogCleanup(owner);
  const ownerRow = owner.locator(".document-row").filter({ hasText: filename });
  await ownerRow.getByRole("button", { name: "Delete" }).click();
  await expect(ownerRow).toHaveCount(0);
  await owner.close();
  await otherStudent.close();
});

function pageDialogCleanup(page: import("@playwright/test").Page) {
  page.once("dialog", dialog => dialog.accept());
}
