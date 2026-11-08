import { expect, test } from "@playwright/test";

const profile = {
  preferred_language: "mixed", learning_pace: "steady",
  proficiencies: [{ subject: null, topic: "Fractions", mastery_score: 60, evidence_attempts: 5, difficulty: "intermediate", strategy: "guided_practice", recommendation: "Try a scaffolded example.", revision_recommended: false, last_activity_at: "2026-01-01T00:00:00Z" }],
  recent_activity: [{ topic: "Fractions", outcome: "correct", occurred_at: "2026-01-01T00:00:00Z" }], revision_topics: [],
};

async function mockClassroom(page, profileFails = false, profileDelay = 0) {
  let prefs = { preferred_language: "mixed", learning_level: "beginner", learning_pace: "steady", learning_goal: null as string | null };
  let contextRequests = 0;
  const preferenceWrites: Array<typeof prefs> = [];
  await page.addInitScript(() => sessionStorage.setItem("bhashalearn_access_token", "int08-e2e-token"));
  await page.route("**/api/v1/**", async route => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/v1", "");
    if (path === "/auth/me") return route.fulfill({ json: { id: "student-1", email: "learner@example.test", display_name: "Learner" } });
    if (path === "/sessions" && route.request().method() === "GET") return route.fulfill({ json: [{ id: "session-1", topic: "Fractions", language: "mixed", created_at: "2026-01-01T00:00:00Z" }] });
    if (path === "/students/me/preferences" && route.request().method() === "GET") return route.fulfill({ json: prefs });
    if (path === "/students/me/preferences" && route.request().method() === "PUT") {
      prefs = route.request().postDataJSON(); preferenceWrites.push({ ...prefs });
      return route.fulfill({ json: prefs });
    }
    if (path === "/students/me/learning-profile") {
      if (profileDelay) await new Promise(resolve => setTimeout(resolve, profileDelay));
      return profileFails
        ? route.fulfill({ status: 503, json: { detail: "Profile service unavailable" } })
        : route.fulfill({ json: { ...profile, preferred_language: prefs.preferred_language, learning_pace: prefs.learning_pace } });
    }
    if (path === "/sessions/session-1/context") {
      contextRequests += 1;
      return route.fulfill({ json: { session_id: "session-1", topic: "Fractions", preferred_language: prefs.preferred_language, learning_level: prefs.learning_level, learning_pace: prefs.learning_pace, learning_goal: prefs.learning_goal, messages: [], visual_lesson: null } });
    }
    if (path === "/tutor/sessions/session-1/lesson-plan") return route.fulfill({ json: {
      session_id: "session-1", evidence_attempts: 5, mastery_score: 60, recommendation_source: "recorded_practice", learning_goal: null, citations: [],
      plan: { learning_objective: "Understand fractions", prerequisite_concepts: ["Equal parts"], explanation_strategy: "Use a scaffolded example", examples: ["One half"], understanding_checks: ["What is half?"], suggested_next_activity: "Try a practice question", difficulty: "intermediate", language: prefs.preferred_language, recommended_topic: null, recommendation_reason: "Keep practising.", fallback: false, grounded: false },
    } });
    return route.fulfill({ status: 404, json: { detail: "Unexpected mocked API request" } });
  });
  return { preferenceWrites, contextCount: () => contextRequests };
}

test("pace persists across language changes and shared context refreshes", async ({ page }) => {
  const state = await mockClassroom(page);
  await page.goto("/classroom");
  const pace = page.getByLabel("Learning pace");
  await expect(pace).toHaveValue("steady");
  await expect(page.getByText("Fractions: 60% mastery")).toBeVisible();

  await pace.selectOption("slow");
  await expect.poll(() => state.preferenceWrites.length).toBe(1);
  expect(state.preferenceWrites[0]).toMatchObject({ learning_pace: "slow", preferred_language: "mixed" });
  await expect(pace).toHaveValue("slow");

  await page.getByLabel("Tutor language").selectOption("english");
  await expect.poll(() => state.preferenceWrites.length).toBe(2);
  expect(state.preferenceWrites[1]).toMatchObject({ learning_pace: "slow", preferred_language: "english" });
  await expect(pace).toHaveValue("slow");
  await expect.poll(state.contextCount).toBeGreaterThan(1);

  await page.getByLabel("Explanation level").selectOption("advanced");
  await expect.poll(() => state.preferenceWrites.length).toBe(3);
  expect(state.preferenceWrites[2]).toMatchObject({ learning_level: "advanced", learning_pace: "slow", preferred_language: "english" });
});

test("learning profile loading and error states are accessible", async ({ page }) => {
  await mockClassroom(page, true, 1500);
  const profileRequest = page.waitForRequest(request => request.url().includes("/students/me/learning-profile"));
  await page.goto("/classroom");
  await profileRequest;
  await expect(page.getByRole("status")).toContainText("Loading learning profile");
  await expect(page.getByRole("alert")).toContainText("Profile service unavailable");
});
