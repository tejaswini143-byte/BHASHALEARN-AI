import { expect, test } from "@playwright/test";

const baseLesson = {
  id: "solar-system",
  subject: { en: "Space science", te: "అంతరిక్ష విజ్ఞానం" },
  topic: { en: "Planetary orbits", te: "గ్రహ కక్ష్యలు" },
  title: { en: "A solar system lesson", te: "సౌర కుటుంబ పాఠం" },
  description: { en: "Explore how planets orbit the Sun.", te: "గ్రహాలు సూర్యుని చుట్టూ ఎలా తిరుగుతాయో చూడండి." },
  objectives: [{ en: "Identify planets.", te: "గ్రహాలను గుర్తించండి." }],
  takeaways: [{ en: "Gravity keeps planets in orbit.", te: "గురుత్వాకర్షణ గ్రహాలను కక్ష్యలో ఉంచుతుంది." }],
  steps: [
    { title: { en: "Meet the Sun", te: "సూర్యుడిని కలుద్దాం" }, explanation: { en: "The Sun's gravity keeps planets in orbit.", te: "సూర్యుని గురుత్వాకర్షణ గ్రహాలను కక్ష్యలో ఉంచుతుంది." } },
    { title: { en: "Select a planet", te: "ఒక గ్రహాన్ని ఎంచుకోండి" }, explanation: { en: "Compare the planet's orbit and year.", te: "గ్రహ కక్ష్య, సంవత్సరాన్ని పోల్చండి." } },
  ],
};
const generatedEnvelope = {
  version: 2,
  lesson: {
    ...baseLesson,
    id: "geometry",
    title: { en: "Cube properties", te: "ఘనం లక్షణాలు" },
    topic: { en: "Cube properties", te: "ఘనం లక్షణాలు" },
    steps: [
      { title: { en: "Inspect the cube", te: "ఘనాన్ని పరిశీలించండి" }, explanation: { en: "A cube has six square faces.", te: "ఘనానికి ఆరు చతురస్ర ముఖాలు ఉంటాయి." }, scene_id: "geometry" },
    ],
    questions: [{ prompt: { en: "How many faces?", te: "ఎన్ని ముఖాలు?" }, answer: { en: "Six", te: "ఆరు" }, explanation: { en: "A cube has six faces.", te: "ఘనానికి ఆరు ముఖాలు ఉంటాయి." } }],
    activities: [{ instruction: { en: "Rotate the cube.", te: "ఘనాన్ని తిప్పండి." }, control: "rotate-shape" }],
    completion_criteria: [{ en: "Describe the faces.", te: "ముఖాలను వివరించండి." }],
  },
  scene: { kind: "geometry", parameters: { shape: "cube", size: 1.5 } },
};

async function configureClassroom(page, generated = false) {
  await page.addInitScript(() => sessionStorage.setItem("bhashalearn_access_token", "feature4-e2e-student-token"));
  const chatMessages: string[] = [];
  await page.route("**/api/v1/**", async route => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/v1", "");
    const method = route.request().method();
    if (path === "/auth/me") return route.fulfill({ json: { id: "feature4-student", email: "student@example.test", display_name: "Visual Learner" } });
    if (path === "/visual-lessons" && method === "GET") return route.fulfill({ json: [{ version: 1, lesson: baseLesson, scene: { kind: baseLesson.id } }] });
    if (path === "/sessions" && url.search === "?limit=100" && method === "GET") return route.fulfill({ json: [{ id: "feature4-session", topic: "Solar system", language: "english", created_at: "2026-01-01T00:00:00Z" }] });
    if (path === "/visual-lessons/session-state" && method === "GET") return route.fulfill({ json: { state: null } });
    if (path === "/visual-lessons/session-state" && method === "PUT") return route.fulfill({ json: { state: null } });
    if (path === "/visual-lessons/generate" && method === "POST" && generated) return route.fulfill({ json: generatedEnvelope });
    if (path === "/tutor/sessions/feature4-session/chat" && method === "POST") {
      const body = route.request().postDataJSON();
      chatMessages.push(body.message);
      return route.fulfill({ json: { session_id: "feature4-session", reply: "Earth orbits the Sun because gravity changes its direction as it moves forward.", language: body.language, learning_level: "beginner", citations: [] } });
    }
    return route.fulfill({ status: 404, json: { detail: `Unexpected mocked request ${method} ${path}` } });
  });
  return chatMessages;
}

test("React Flow steps explain in context through the shared tutor session", async ({ page }) => {
  const messages = await configureClassroom(page);
  await page.goto("/visual-lessons");
  await expect(page.getByRole("heading", { name: "A solar system lesson" })).toBeVisible();
  const secondStep = page.locator(".react-flow__node").filter({ hasText: "2. Select a planet" });
  await secondStep.click();
  await expect(page.locator(".vl-flow-explanation")).toContainText("Compare the planet's orbit and year.");
  await page.getByLabel("Ask about this lesson").fill("Why do planets stay in orbit?");
  await page.getByRole("button", { name: "Ask teacher" }).click();
  await expect(page.getByText(/Earth orbits the Sun because gravity/)).toBeVisible();
  expect(messages).toHaveLength(1);
  expect(messages[0]).toContain("Current step 2: Select a planet");
  expect(messages[0]).toContain("Student question: Why do planets stay in orbit?");
});

test("validated Gemini lesson renders Telugu content and interactive question", async ({ page }) => {
  await configureClassroom(page, true);
  await page.goto("/visual-lessons");
  await page.getByLabel("Create a bilingual lesson with Gemini").fill("Cube properties");
  await page.getByRole("button", { name: "Generate lesson" }).click();
  await expect(page.getByRole("heading", { name: "Cube properties" })).toBeVisible();
  await page.getByLabel("Explanation language").selectOption("te");
  await expect(page.getByText("ఘనాన్ని పరిశీలించండి", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "ఎన్ని ముఖాలు?" })).toBeVisible();
  await page.getByLabel("మీ సమాధానం").fill("ఆరు");
  await page.getByRole("button", { name: "సమాధానం తనిఖీ చేయి" }).click();
  await expect(page.getByRole("status").filter({ hasText: "సరైనది" })).toBeVisible();
});
