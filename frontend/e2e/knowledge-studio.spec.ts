import { expect, test } from "@playwright/test";

const documentItem = {
  id: "doc-studio-1", original_filename: "fractions.pdf", mime_type: "application/pdf",
  file_size_bytes: 1024, page_count: 2, processing_status: "processed",
  processing_error_code: null, created_at: "2026-11-08T10:00:00Z", updated_at: "2026-11-08T10:00:00Z",
};

test("student uploads a PDF, selects it, and asks a cited document question", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("bhashalearn_access_token", "playwright-test-token"));
  await page.route("**/api/v1/documents?limit=100", route => route.fulfill({ json: [documentItem] }));
  await page.route("**/api/v1/documents/doc-studio-1/index-status", route => route.fulfill({ json: { document_id: "doc-studio-1", status: "ready", error_code: null, chunk_count: 2, embedding_model: "mock", embedding_dimensions: 768, updated_at: documentItem.updated_at } }));
  await page.route("**/api/v1/documents", async route => {
    if (route.request().method() === "POST") await route.fulfill({ status: 201, json: documentItem });
    else await route.fulfill({ json: [documentItem] });
  });
  await page.route("**/api/v1/knowledge/ask", route => route.fulfill({ json: {
    answer: "A half is one of two equal parts. [S1]\n\nSources / మూలాలు: [S1] fractions.pdf (p. 2)",
    citations: [{ citation_id: "S1", document_id: "doc-studio-1", document_title: "fractions.pdf", page_number: 2 }],
    grounded: true, retrieval_used: true, uncertainty: null,
  } }));

  await page.goto("/documents");
  await page.getByLabel("Choose PDF file").setInputFiles({ name: "fractions.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 synthetic test file") });
  await page.getByRole("button", { name: "Upload PDF" }).click();
  await expect(page.getByRole("status").filter({ hasText: "PDF uploaded" })).toBeVisible();

  await page.goto("/knowledge-studio");
  await page.getByLabel(/fractions\.pdf/).check();
  await page.getByLabel("Ask a question about your selected documents").fill("What is a half?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByText("A half is one of two equal parts.")).toBeVisible();
  await expect(page.getByRole("link", { name: /fractions\.pdf · page 2/ })).toHaveAttribute("href", /page=2/);
});
