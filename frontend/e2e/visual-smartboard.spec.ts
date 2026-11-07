import { expect, test } from "@playwright/test";

test("authenticated visual studio provides an interactive smartboard and sample lesson playback", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("bhashalearn_access_token", "adv04-e2e-token"));
  await page.route("**/api/v1/**", async route => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/v1", "");
    if (path === "/sessions" && route.request().method() === "GET") return route.fulfill({ json: [{ id: "adv04-session", topic: "Geometry", language: "mixed", created_at: "2026-01-01T00:00:00Z" }] });
    if (path === "/students/me/preferences") return route.fulfill({ json: { preferred_language: "mixed" } });
    if (path === "/sessions/adv04-session/context") return route.fulfill({ json: { session_id: "adv04-session", topic: "Geometry", preferred_language: "mixed", learning_level: "beginner", learning_goal: null, messages: [], visual_lesson: { visual_key: "dijkstra-shortest-path", title: "Dijkstra's Shortest Path", concept: "Graph paths", description: "Sample", start_node: "A", end_node: "F", updated_at: "2026-01-01T00:00:00Z" } } });
    if (path === "/progress/Geometry") return route.fulfill({ json: { mastery_score: 0, evidence_attempts: 0, correct_attempts: 0, incorrect_attempts: 0, evidence_status: "not_assessed", difficulty: "beginner", strategy: "guided", recommendation: "Explore the lesson." } });
    if (route.request().method() === "PUT") return route.fulfill({ json: {} });
    return route.fulfill({ status: 404, json: { detail: "Unexpected mocked API request" } });
  });
  await page.goto("/visual");
  await expect(page.getByRole("heading", { name: "Dijkstra's Shortest Path" })).toBeVisible();
  await page.getByRole("button", { name: "✦ Smartboard" }).click();
  await expect(page.getByRole("application", { name: /Interactive smartboard/ })).toBeVisible();
  await page.getByLabel("Sample lesson").selectOption("pythagoras");
  await page.getByRole("button", { name: "Next lesson step" }).click();
  await expect(page.getByRole("heading", { name: "Find the right angle" })).toBeVisible();
  await page.getByRole("button", { name: /a = 3:/ }).click();
  await expect(page.getByText("The shorter leg has length 3.")).toBeVisible();

  const board = page.getByRole("application", { name: /Interactive smartboard/ });
  const bounds = await board.boundingBox();
  if (!bounds) throw new Error("Smartboard did not receive a visible layout box.");
  await page.getByRole("button", { name: "Draw freely" }).click();
  await page.mouse.move(bounds.x + bounds.width * 0.15, bounds.y + bounds.height * 0.75);
  await page.mouse.down();
  await page.mouse.move(bounds.x + bounds.width * 0.22, bounds.y + bounds.height * 0.80, { steps: 4 });
  await page.mouse.up();
  await expect(board.locator("[data-object-id^='student-drawing']")).toHaveCount(1);
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(board.locator("[data-object-id^='student-drawing']")).toHaveCount(0);
  await page.getByRole("button", { name: "Redo" }).click();
  await expect(board.locator("[data-object-id^='student-drawing']")).toHaveCount(1);
  await page.getByRole("button", { name: "13", exact: true }).click();
  await page.getByRole("button", { name: "Check answer" }).click();
  await expect(page.getByRole("status")).toContainText("Correct");

  await page.getByLabel("Sample lesson").selectOption("solar-system");
  await expect(page.getByRole("heading", { name: "A tour of the solar system" })).toBeVisible();
  await page.getByRole("button", { name: "Play lesson" }).click();
  await expect(page.getByRole("heading", { name: "Start with the Sun" })).toBeVisible();
});
