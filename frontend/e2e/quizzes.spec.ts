import { expect, test } from "@playwright/test";

const quiz = {
  quiz_id: "3bc436e7-5989-4f6a-8621-f577a47f8e6d",
  session_id: "1f60632a-c962-4d8e-a9c6-8f7760e75b89",
  subject: "Mathematics",
  topic: "equivalent fractions",
  language: "mixed",
  difficulty: "beginner",
  adaptive_difficulty: true,
  source: "mixed",
  questions: [
    { attempt_id: "0f2bdd5f-7ea2-4c15-8a2b-20c682cc3f0a", question_id: "fractions-01", position: 1, type: "multiple_choice", difficulty: "beginner", source: "curated", prompt: "Which fraction is equivalent to 1/2?\nWhich fraction is equivalent to 1/2? (తెలుగు అభ్యాసం) — English choices", options: ["2/4", "2/3", "3/5", "4/5"] },
    { attempt_id: "c48e11ef-7947-40e9-9b88-5986af5a351a", question_id: "fractions-tf-01", position: 2, type: "true_false", difficulty: "beginner", source: "deterministic_fallback", prompt: "Multiplying the numerator and denominator by the same nonzero number makes an equivalent fraction.\nలవం, హారాన్ని ఒకే సున్నా కాని సంఖ్యతో గుణిస్తే సమాన భిన్నం వస్తుంది. (True/False)", options: ["True / నిజం", "False / తప్పు"] },
  ],
};

test("adaptive quiz supports language switching, answers, progress, and explanations", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("bhashalearn_access_token", "mock-student-token"));
  let createPayload: Record<string, unknown> | null = null;
  await page.route("**/api/v1/quizzes/catalog", route => route.fulfill({ json: [
    { subject: "Mathematics", topic: "equivalent fractions", question_count: 6, difficulties: ["beginner", "intermediate", "advanced"] },
  ] }));
  await page.route("**/api/v1/quizzes/history", route => route.fulfill({ json: [] }));
  await page.route("**/api/v1/quizzes", async route => {
    if (route.request().method() === "POST") { createPayload = route.request().postDataJSON(); await route.fulfill({ status: 201, json: quiz }); }
    else await route.continue();
  });
  await page.route(`**/api/v1/quizzes/${quiz.quiz_id}/submit`, async route => {
    const body = route.request().postDataJSON();
    expect(body.answers).toHaveLength(2);
    await route.fulfill({ json: {
      quiz_id: quiz.quiz_id, subject: quiz.subject, topic: quiz.topic, language: "mixed", difficulty: "beginner",
      question_count: 2, score: 2, mastery_score: 100, completed: true, issued_at: "2026-11-08T10:00:00Z",
      topic_recommendation: "Try a new question with less scaffolding.", replayed: false,
      questions: [
        { attempt_id: quiz.questions[0].attempt_id, question_id: "fractions-01", position: 1, type: "multiple_choice", prompt: quiz.questions[0].prompt, answer: "2/4", is_correct: true, correct_answer: "2/4", explanation: "Multiply both parts by 2." },
        { attempt_id: quiz.questions[1].attempt_id, question_id: "fractions-tf-01", position: 2, type: "true_false", prompt: quiz.questions[1].prompt, answer: "True / నిజం", is_correct: true, correct_answer: "true", explanation: "The value stays equal." },
      ],
    } });
  });
  await page.goto("/quizzes");
  await expect(page.getByRole("heading", { name: "Quiz your way." })).toBeVisible();
  await page.getByRole("combobox").nth(2).selectOption("english");
  await page.getByRole("button", { name: /Start assessment/ }).click();
  await expect.poll(() => createPayload?.language).toBe("english");
  await expect(page.getByText("Question 1 of 2")).toBeVisible();
  await page.getByLabel("2/4").check();
  await page.getByRole("button", { name: "Next question →" }).click();
  await expect(page.getByText("Question 2 of 2")).toBeVisible();
  await page.getByLabel("True / నిజం").check();
  await page.getByRole("button", { name: /Submit assessment/ }).click();
  await expect(page.getByRole("group", { name: "Confirm quiz submission" })).toBeVisible();
  await page.getByRole("button", { name: "Confirm" }).click();
  await expect(page.getByRole("heading", { name: "Strong work. Keep stretching your skills." })).toBeVisible();
  await expect(page.getByText("Multiply both parts by 2.")).toBeVisible();
  await expect(page.getByText("Try a new question with less scaffolding.")).toBeVisible();
});

test("quiz setup remains usable without horizontal overflow on a narrow screen", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() => sessionStorage.setItem("bhashalearn_access_token", "mock-student-token"));
  await page.route("**/api/v1/quizzes/catalog", route => route.fulfill({ json: [
    { subject: "Mathematics", topic: "equivalent fractions", question_count: 6, difficulties: ["beginner", "intermediate", "advanced"] },
  ] }));
  await page.route("**/api/v1/quizzes/history", route => route.fulfill({ json: [] }));
  await page.goto("/quizzes");
  await expect(page.getByLabel("Subject and topic")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
});

test("quiz setup shows an accessible offline error when mocked services are unavailable", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("bhashalearn_access_token", "mock-student-token"));
  await page.route("**/api/v1/quizzes/catalog", route => route.abort());
  await page.route("**/api/v1/quizzes/history", route => route.fulfill({ json: [] }));
  await page.goto("/quizzes");
  await expect(page.getByRole("alert")).toContainText("Quiz service is offline");
});
