import { expect, test, type Page } from "@playwright/test";

type Memory = { id: string; topic: string; note: string; created_at: string };
const date = "2026-10-01T00:00:00Z";

async function mockMemoryApi(page: Page, initial: Memory[] = []) {
  const memories = [...initial];
  await page.addInitScript(() => sessionStorage.setItem("bhashalearn_access_token", "browser-test-token"));
  await page.route("**/api/v1/**", async route => {
    const request = route.request();
    const url = new URL(request.url());
    expect(request.headers().authorization).toBe("Bearer browser-test-token");
    if (url.pathname.endsWith("/auth/me")) {
      await route.fulfill({ json: { id: "student-1", email: "learner@example.test", display_name: "Test Learner" } });
      return;
    }
    if (url.pathname.endsWith("/memories") && request.method() === "GET") {
      await route.fulfill({ json: memories }); return;
    }
    if (url.pathname.endsWith("/memories") && request.method() === "POST") {
      const input = request.postDataJSON();
      const memory = { id: `memory-${Date.now()}`, ...input, created_at: date };
      memories.unshift(memory);
      await route.fulfill({ status: 201, json: memory }); return;
    }
    const id = decodeURIComponent(url.pathname.split("/").at(-1) || "");
    if (request.method() === "PATCH") {
      const index = memories.findIndex(item => item.id === id);
      if (index < 0) { await route.fulfill({ status: 404, json: { detail: "Memory not found" } }); return; }
      memories[index] = { ...memories[index], ...request.postDataJSON() };
      await route.fulfill({ json: memories[index] }); return;
    }
    if (request.method() === "DELETE") {
      const index = memories.findIndex(item => item.id === id);
      if (index >= 0) memories.splice(index, 1);
      await route.fulfill({ status: 204, body: "" }); return;
    }
    await route.fulfill({ status: 404, json: { detail: "Not found" } });
  });
}

test("student can list, create, correct, and confirm deletion of memories", async ({ page }) => {
  await mockMemoryApi(page, [{ id: "memory-existing", topic: "Fractions", note: "Use visual examples", created_at: date }]);
  await page.goto("/memories");
  await expect(page.getByRole("heading", { name: "Fractions" })).toBeVisible();
  await page.getByLabel("Topic").fill("Decimals");
  await page.getByLabel("What should your tutor remember?").fill("Use a number line");
  await page.getByRole("button", { name: "Save memory" }).click();
  await expect(page.getByRole("heading", { name: "Decimals" })).toBeVisible();
  await expect(page.getByRole("status")).toContainText("Memory saved");

  const decimals = page.locator(".memory-item").filter({ has: page.getByRole("heading", { name: "Decimals" }) });
  await decimals.getByRole("button", { name: "Correct" }).click();
  await page.getByLabel("What should your tutor remember?").fill("Show equivalent decimals");
  await page.getByRole("button", { name: "Save correction" }).click();
  await expect(decimals).toContainText("Show equivalent decimals");
  page.once("dialog", dialog => dialog.accept());
  await decimals.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByRole("heading", { name: "Decimals" })).toHaveCount(0);
  await expect(page.getByRole("status")).toContainText("Memory deleted");
});

test("missing and rejected authentication cannot access the memory screen", async ({ page }) => {
  await page.goto("/memories");
  await expect(page).toHaveURL(/\/login$/);

  await page.addInitScript(() => sessionStorage.setItem("bhashalearn_access_token", "expired-token"));
  await page.route("**/api/v1/**", route => route.fulfill({ status: 401, json: { detail: "Invalid token" } }));
  await page.goto("/memories");
  await expect(page).toHaveURL(/\/login$/);
});

test("memory API errors are shown to the student", async ({ page }) => {
  await mockMemoryApi(page);
  await page.route("**/api/v1/memories", route => route.request().method() === "POST"
    ? route.fulfill({ status: 422, json: { detail: "Memory note is too long" } })
    : route.continue());
  await page.goto("/memories");
  await page.getByLabel("Topic").fill("Fractions");
  await page.getByLabel("What should your tutor remember?").fill("Some context");
  await page.getByRole("button", { name: "Save memory" }).click();
  await expect(page.getByRole("alert")).toContainText("Memory note is too long");
});
