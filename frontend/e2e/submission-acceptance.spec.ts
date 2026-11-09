import { expect, test } from "@playwright/test";

const student = { id: "submission-student", email: "learner@example.test", display_name: "Test Learner" };
const session = { id: "submission-session", topic: "Fractions", language: "mixed", created_at: "2026-11-09T08:00:00Z" };
const prefs = { preferred_language: "mixed", learning_level: "beginner", learning_pace: "steady", learning_goal: null };

test("registration validates input, registers, signs in, and reaches the protected dashboard", async ({ page }) => {
  const calls: string[] = [];
  await page.route("**/api/v1/**", async route => {
    const path = new URL(route.request().url()).pathname;
    calls.push(`${route.request().method()} ${path}`);
    if (path.endsWith("/auth/register")) return route.fulfill({ status: 201, json: student });
    if (path.endsWith("/auth/login")) return route.fulfill({ json: { access_token: "submission-mock-token", token_type: "bearer" } });
    if (path.endsWith("/auth/me")) return route.fulfill({ json: student });
    if (path.endsWith("/students/me/preferences")) return route.fulfill({ json: prefs });
    if (path.endsWith("/students/me/progress")) return route.fulfill({ json: [] });
    if (path.endsWith("/sessions")) return route.fulfill({ json: [] });
    return route.fulfill({ status: 200, json: [] });
  });

  await page.goto("/register");
  await page.getByRole("button", { name: /create account/i }).click();
  await expect(page.getByLabel("Your name")).toHaveAttribute("required", "");
  await page.getByLabel("Your name").fill(student.display_name);
  await page.getByLabel("Email address").fill(student.email);
  await page.locator('input[autocomplete="new-password"]').fill("synthetic-submission-password");
  await page.getByRole("button", { name: /create account/i }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  expect(calls).toContain("POST /api/v1/auth/register");
  expect(calls).toContain("POST /api/v1/auth/login");
  await expect(page.getByRole("navigation", { name: "Dashboard navigation" })).toBeVisible();
});

test("classroom delivers a bilingual exchange and persists the tutor response", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("bhashalearn_access_token", "submission-mock-token"));
  const messages: Array<{ id: string; role: "user" | "assistant"; content: string; created_at: string }> = [];
  let submittedLanguage = "";
  await page.route("**/api/v1/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path.endsWith("/auth/me")) return route.fulfill({ json: student });
    if (path.endsWith("/sessions") && request.method() === "GET") return route.fulfill({ json: [session] });
    if (path.endsWith("/students/me/preferences")) return route.fulfill({ json: prefs });
    if (path.endsWith("/students/me/learning-profile")) return route.fulfill({ json: { preferred_language: "mixed", learning_pace: "steady", proficiencies: [], recent_activity: [], revision_topics: [] } });
    if (path.endsWith(`/sessions/${session.id}/context`)) return route.fulfill({ json: { session_id: session.id, topic: session.topic, preferred_language: "mixed", learning_level: "beginner", learning_pace: "steady", learning_goal: null, messages, visual_lesson: null } });
    if (path.includes("/learning-plan")) return route.fulfill({ status: 404, json: { detail: "No plan available" } });
    if (path.endsWith(`/tutor/sessions/${session.id}/chat`) && request.method() === "POST") {
      const input = request.postDataJSON() as { message: string };
      submittedLanguage = input.message;
      messages.push({ id: "student-turn", role: "user", content: input.message, created_at: "2026-11-09T08:01:00Z" });
      messages.push({ id: "tutor-turn", role: "assistant", content: "ఒక సగం అంటే రెండు సమాన భాగాల్లో ఒకటి (one of two equal parts).", created_at: "2026-11-09T08:01:01Z" });
      return route.fulfill({ json: { session_id: session.id, reply: messages[1].content, language: "mixed", learning_level: "beginner" } });
    }
    if (path.endsWith(`/sessions/${session.id}/messages`)) return route.fulfill({ json: messages });
    return route.fulfill({ status: 200, json: [] });
  });

  await page.goto(`/classroom?session=${session.id}`);
  await expect(page.getByRole("heading", { name: /ready to explore Fractions/i })).toBeVisible();
  await page.getByLabel("Message your AI tutor").fill("Explain one half in Telugu and English");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByText("ఒక సగం అంటే రెండు సమాన భాగాల్లో ఒకటి (one of two equal parts).", { exact: true })).toBeVisible();
  expect(submittedLanguage).toBe("Explain one half in Telugu and English");
  await expect(page.getByText("Explain one half in Telugu and English", { exact: true })).toBeVisible();
});

test("PDF research search sends a query and presents its document and page citation", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("bhashalearn_access_token", "submission-mock-token"));
  let searchBody: { query: string; top_k: number } | null = null;
  await page.route("**/api/v1/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path.endsWith("/documents") && request.method() === "GET") return route.fulfill({ json: [] });
    if (path.endsWith("/documents/search") && request.method() === "POST") {
      searchBody = request.postDataJSON();
      return route.fulfill({ json: { items: [{ chunk_id: "mock-chunk", document_id: "mock-doc", document_name: "Fractions.pdf", page_number: 2, ordinal: 0, content: "Equivalent fractions multiply numerator and denominator by the same number.", score: 0.94 }] } });
    }
    return route.fulfill({ status: 200, json: [] });
  });

  await page.goto("/documents");
  await expect(page.getByRole("heading", { name: "Documents", exact: true })).toBeVisible();
  await page.getByLabel("Search your study materials").fill("How do equivalent fractions work?");
  await page.getByRole("button", { name: "Search" }).click();
  await expect(page.getByText("Equivalent fractions multiply numerator and denominator by the same number.")).toBeVisible();
  await expect(page.getByText("Page 2 · Similarity 94.0%", { exact: true })).toBeVisible();
  expect(searchBody).toEqual({ query: "How do equivalent fractions work?", top_k: 5 });
});

test("assistant workspace loads a session and shows the saved bilingual exchange", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("bhashalearn_access_token", "submission-mock-token"));
  const messages: Array<{ id: string; role: "user" | "assistant"; content: string; created_at: string }> = [];
  await page.route("**/api/v1/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path.endsWith("/auth/me")) return route.fulfill({ json: student });
    if (path.endsWith("/sessions") && request.method() === "GET") return route.fulfill({ json: [session] });
    if (path.endsWith(`/sessions/${session.id}/context`)) return route.fulfill({ json: { session_id: session.id, topic: session.topic, preferred_language: "mixed", learning_level: "beginner", learning_pace: "steady", learning_goal: null, messages, visual_lesson: null } });
    if (path.endsWith(`/tutor/sessions/${session.id}/chat`) && request.method() === "POST") {
      const input = request.postDataJSON() as { message: string };
      messages.splice(0, messages.length,
        { id: "assistant-question", role: "user", content: input.message, created_at: "2026-11-09T08:02:00Z" },
        { id: "assistant-reply", role: "assistant", content: "ఒకటి రెండు సమాన భాగాల్లో ఒకటి (one out of two equal parts).", created_at: "2026-11-09T08:02:01Z" });
      return route.fulfill({ json: { session_id: session.id, reply: messages[1].content, language: "mixed", learning_level: "beginner" } });
    }
    if (path.endsWith(`/sessions/${session.id}/messages`)) return route.fulfill({ json: messages });
    return route.fulfill({ status: 200, json: [] });
  });

  await page.goto(`/chat?session=${session.id}`);
  await expect(page.getByRole("heading", { name: "Fractions" })).toBeVisible();
  await page.getByLabel("Message to AI tutor").fill("Explain fractions in Telugu and English");
  await page.getByRole("button", { name: /send/i }).click();
  await expect(page.getByText("ఒకటి రెండు సమాన భాగాల్లో ఒకటి (one out of two equal parts).", { exact: true })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Saved conversations" })).toContainText("Fractions");
});
