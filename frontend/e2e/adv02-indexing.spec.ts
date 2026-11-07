import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import { makeTwoPagePdf, openDocuments, signIn } from "./helpers";

test("authenticated student uploads, indexes, searches, reindexes, and deletes a synthetic PDF", async ({ page }) => {
  test.skip(process.env.BHASHALEARN_E2E_ALLOW_MUTATIONS !== "1" || process.env.BHASHALEARN_E2E_FAKE_EMBEDDINGS !== "1", "Requires an explicitly isolated database and the test-only deterministic embedding provider.");

  const suffix = randomUUID();
  const email = `adv02-e2e-${suffix}@example.com`;
  const password = `Aa1!${randomUUID()}-synthetic`;
  const registration = await page.request.post("/api/v1/auth/register", { data: { email, display_name: "ADV-02 browser fixture", password } });
  expect(registration.status()).toBe(201);

  let documentId: string | undefined;
  let token: string | null = null;
  try {
    await signIn(page, email, password);
    await openDocuments(page);
    await page.getByLabel("Choose PDF file").setInputFiles({
      name: `adv02-synthetic-${suffix}.pdf`,
      mimeType: "application/pdf",
      buffer: makeTwoPagePdf("Telugu fractions lesson: one half is 1/2", "Practice fractions with Telugu number words"),
    });
    const uploaded = page.waitForResponse(response => response.url().includes("/api/v1/documents") && response.request().method() === "POST");
    await page.getByRole("button", { name: "Upload PDF" }).click();
    const uploadResponse = await uploaded;
    expect(uploadResponse.status()).toBe(201);
    documentId = (await uploadResponse.json() as { id: string }).id;
    token = await page.evaluate(() => sessionStorage.getItem("bhashalearn_access_token"));

    const row = page.locator(".document-row").filter({ hasText: `adv02-synthetic-${suffix}.pdf` });
    await row.getByRole("link", { name: "View" }).click();
    const indexRequest = page.waitForResponse(response => response.url().includes(`/api/v1/documents/${documentId}/index`) && response.request().method() === "POST");
    await page.getByRole("button", { name: "Index document" }).click();
    const indexResponse = await indexRequest;
    expect(indexResponse.status()).toBe(200);
    expect((await indexResponse.json() as { status: string }).status).toBe("ready");
    await expect(page.getByText(/chunks indexed with gemini-embedding-001/i)).toBeVisible();

    const reindexRequest = page.waitForResponse(response => response.url().includes(`/api/v1/documents/${documentId}/index?force=true`) && response.request().method() === "POST");
    await page.getByRole("button", { name: "Reindex document" }).click();
    expect((await reindexRequest).status()).toBe(200);

    await page.getByRole("link", { name: /all documents/i }).click();
    await page.getByLabel("Search your study materials").fill("Telugu fractions");
    await page.getByRole("button", { name: "Search" }).click();
    await expect(page.getByText("Telugu fractions lesson: one half is 1/2")).toBeVisible();
    await expect(page.getByText(/Page 1 · Similarity 100.0%/)).toBeVisible();

    page.once("dialog", dialog => dialog.accept());
    const deletion = page.waitForResponse(response => response.url().includes(`/api/v1/documents/${documentId}`) && response.request().method() === "DELETE");
    await row.getByRole("button", { name: "Delete" }).click();
    expect((await deletion).status()).toBe(204);
    await expect(row).toHaveCount(0);
    await page.getByRole("button", { name: "Search" }).click();
    await expect(page.getByText("No indexed documents matched your search.")).toBeVisible();
  } finally {
    if (documentId && token) {
      await page.request.delete(`/api/v1/documents/${documentId}`, { headers: { Authorization: `Bearer ${token}` } }).catch(() => undefined);
    }
  }
});
