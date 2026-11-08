import { expect, test } from "@playwright/test";

test("research workspace shows cited offline results and prepares an approved non-executable task", async ({ page }) => {
  const now = "2026-11-08T10:00:00Z";
  const sources = [{ id: "source-1", title: "Khan Academy photosynthesis", canonical_url: "https://www.khanacademy.org/science/biology", publisher: "Khan Academy", excerpt: "Plants store energy through photosynthesis.", retrieved_at: now }];
  const session = { id: "research-1", question: "How does photosynthesis work?", language: "mixed", status: "completed", provider_mode: "offline_demo", summary: { overview: "తెలుగు + English study summary: review one source.", summary_mode: "excerpt_fallback", findings: [{ text: "Plants store energy.", source_indices: [1] }], contradictions: [], uncertainties: ["Excerpt is not independently verified."], follow_up: ["Khan Academy photosynthesis"] }, sources, created_at: now };
  let task: Record<string, unknown> | null = null;
  await page.addInitScript(() => sessionStorage.setItem("bhashalearn_access_token", "mock-student-token"));
  await page.route("**/api/v1/**", async route => {
    const url = new URL(route.request().url()); const method = route.request().method();
    if (url.pathname.endsWith("/auth/me")) return route.fulfill({ json: { id: "student-1", email: "learner@example.com", display_name: "Learner" } });
    if (url.pathname.endsWith("/research/sessions") && method === "GET") return route.fulfill({ json: task ? [session] : [] });
    if (url.pathname.endsWith("/research/tasks") && method === "GET") return route.fulfill({ json: task ? [task] : [] });
    if (url.pathname.endsWith("/research/sessions") && method === "POST") return route.fulfill({ status: 201, json: { ...session, status: "drafted", summary: null, sources: [] } });
    if (url.pathname.endsWith("/research-1/run")) return route.fulfill({ json: session });
    if (url.pathname.endsWith("/research-1")) return route.fulfill({ json: session });
    if (url.pathname.endsWith("/research/tasks") && method === "POST") { task = { id: "task-1", action_type: "study_checklist", title: "Study checklist", payload: {}, status: "drafted", approval_expires_at: null, executable: false, execution_notice: "External browser actions are unavailable; this approved plan was not executed." }; return route.fulfill({ status: 201, json: task }); }
    if (url.pathname.endsWith("/request-approval")) { task = { ...task!, status: "awaiting_approval", approval_expires_at: now }; return route.fulfill({ json: task }); }
    if (url.pathname.endsWith("/approve")) { task = { ...task!, status: "approved" }; return route.fulfill({ json: task }); }
    return route.fulfill({ json: [] });
  });
  await page.goto("/research");
  await expect(page.getByRole("heading", { name: "Explore with evidence." })).toBeVisible();
  await page.getByLabel("What do you want to research?").fill("How does photosynthesis work?");
  await page.getByRole("button", { name: /Start research/ }).click();
  await expect(page.getByText("OFFLINE DEMONSTRATION · FIXTURE SOURCES")).toBeVisible();
  await expect(page.getByRole("link", { name: /Khan Academy photosynthesis/ })).toHaveAttribute("href", sources[0].canonical_url);
  await page.getByRole("button", { name: "Prepare study checklist" }).click();
  await page.getByRole("button", { name: "Request approval" }).click();
  await page.getByRole("button", { name: "Approve plan" }).click();
  await expect(page.getByText("approved", { exact: true })).toBeVisible();
  await expect(page.getByRole("status").getByText(/External browser actions are unavailable/)).toBeVisible();
});
