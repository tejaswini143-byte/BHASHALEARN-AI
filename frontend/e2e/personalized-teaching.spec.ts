import { expect, test } from "@playwright/test";

const lessonResponse = {
  session_id: "session-1", evidence_attempts: 0, mastery_score: null,
  recommendation_source: "no_history", learning_goal: null, citations: [],
  plan: {
    learning_objective: "Explain the idea of halves and use it in an example.",
    prerequisite_concepts: ["Equal groups"], explanation_strategy: "Use one small idea at a time.",
    examples: ["Split one apple into two equal parts."], understanding_checks: ["What does one half mean?"],
    suggested_next_activity: "Try a short example.", difficulty: "beginner", language: "mixed",
    recommended_topic: null, recommendation_reason: "No course sequence yet.", fallback: true, grounded: false,
  },
};

test("personalized classroom lesson supports actions and explicit confusion with mocked APIs", async ({ page }) => {
  const planCalls: Array<{ action?: string; student_response?: string }> = [];
  await page.addInitScript(() => sessionStorage.setItem("bhashalearn_access_token", "mock-token"));
  await page.route("**/api/v1/**", async route => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (path.endsWith("/auth/me")) return route.fulfill({ json: { id: "student-1", email: "learner@example.test", display_name: "Learner" } });
    if (path.endsWith("/sessions") && route.request().method() === "GET") return route.fulfill({ json: [{ id: "session-1", topic: "Fractions", language: "mixed", created_at: new Date().toISOString() }] });
    if (path.endsWith("/students/me/preferences")) return route.fulfill({ json: { preferred_language: "mixed", learning_level: "beginner", learning_pace: "steady", learning_goal: null } });
    if (path.endsWith("/sessions/session-1/context")) return route.fulfill({ json: { session_id: "session-1", topic: "Fractions", preferred_language: "mixed", learning_level: "beginner", learning_pace: "steady", learning_goal: null, messages: [], visual_lesson: null } });
    if (path.endsWith("/students/me/learning-profile")) return route.fulfill({ json: { preferred_language: "mixed", learning_pace: "steady", proficiencies: [], recent_activity: [], revision_topics: [] } });
    if (path.endsWith("/tutor/sessions/session-1/lesson-plan")) {
      if (route.request().postData()) planCalls.push(JSON.parse(route.request().postData()!));
      return route.fulfill({ json: lessonResponse });
    }
    return route.fulfill({ json: [] });
  });
  await page.goto("/classroom?session=session-1");
  await expect(page.getByRole("heading", { name: "Your lesson plan" })).toBeVisible();
  await expect(page.getByText("Explain the idea of halves and use it in an example.")).toBeVisible();
  await expect(page.getByText("AI lesson service is unavailable. Showing a deterministic lesson plan.")).toBeVisible();
  await page.getByRole("button", { name: "Explain more simply" }).click();
  await expect.poll(() => planCalls.at(-1)?.action).toBe("simpler");
  await page.getByLabel("Your response").fill("I'm confused about halves");
  await page.getByRole("button", { name: "Submit response" }).click();
  await expect.poll(() => planCalls.at(-1)?.student_response).toBe("I'm confused about halves");
  await expect(page.getByText("Thanks for trying the check. Your response does not change recorded mastery.")).toBeVisible();
});
