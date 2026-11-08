import { expect, test } from "@playwright/test";

const phase = (completed = false) => ({
  id: "software-developer-digital-literacy", skill_key: "digital-literacy", title: "Digital literacy", title_te: "డిజిటల్ అక్షరాస్యత",
  position: 1, prerequisite_skills: [], course_id: "course-1", course_title: "Digital literacy basics", lesson_id: "lesson-1", lesson_title: "Getting started",
  practice: "Complete a digital literacy practice task.", practice_te: "డిజిటల్ అక్షరాస్యత అభ్యాసం చేయండి.",
  assessment: "Check your understanding of Digital literacy.", assessment_topic: null, project: "Add a digital literacy example to a portfolio project.",
  milestone_description: "Complete the Digital literacy learning and practice steps.", milestone_description_te: "డిజిటల్ అక్షరాస్యత దశలను పూర్తి చేయండి.",
  estimated_hours: 4, milestone_id: "software-developer-digital-literacy-complete", completed,
});
const roadmap = (completed = false) => ({
  goal_id: "goal-1", career_key: "software-developer", career_title: "Software developer", summary: "A general learning path. Not a real-time employment forecast.",
  summary_te: "సాధారణ అభ్యాస మార్గం", language: "mixed", phases: [phase(completed)], weekly_plan: [{ day: "Monday", minutes: 60, activity: "Learn" }],
  total_estimated_hours: 4, planner: "deterministic_catalog_fallback",
  skill_gaps: [{ skill_key: "digital-literacy", name: "Digital literacy", status: "recommended_next", self_assessed_proficiency: null, verified: false }],
  progress: { completed_milestones: completed ? 1 : 0, total_milestones: 1 },
});

test("student builds a roadmap and completes a milestone", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("bhashalearn_access_token", "playwright-token"));
  let currentPlan = roadmap();
  await page.route("**/api/v1/courses/**", route => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ title: "Getting started", content: "A short catalog lesson." }) }));
  await page.route("**/api/v1/career/**", async route => {
    const url = new URL(route.request().url());
    const method = route.request().method();
    let body: unknown = {};
    if (url.pathname.endsWith("/directions")) body = { directions: [
      { career_key: "software-developer", title: "Software developer", required_skills: ["digital-literacy"] },
      { career_key: "web-developer", title: "Web developer", required_skills: ["web-basics"] },
      { career_key: "custom", title: "Custom learning goal", required_skills: ["digital-literacy"] },
    ] };
    else if (url.pathname.endsWith("/skills")) body = { skills: { "digital-literacy": { name: "Digital literacy", prerequisites: [] } }, profile: [] };
    else if (url.pathname.endsWith("/goals") && method === "GET") body = [];
    else if (url.pathname.endsWith("/goals") && method === "POST") body = { id: "goal-1", career_key: "software-developer", career_title: "Software developer", education_level: "beginner", interests: ["apps"], weekly_minutes: 300, preferred_language: "mixed" };
    else if (url.pathname.endsWith("/roadmap") && method === "POST") body = currentPlan;
    else if (url.pathname.includes("/milestones/")) { currentPlan = roadmap(true); body = currentPlan; }
    else if (url.pathname.endsWith("/skills") && method === "PUT") body = { profile: [], evidence_type: "self_reported_only" };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.goto("/career");
  await expect(page.getByRole("heading", { name: "Build your career roadmap" })).toBeVisible();
  await page.getByLabel("Software developer", { exact: false }).check();
  await page.getByLabel("Interests").fill("apps");
  await page.getByRole("button", { name: "Create my roadmap" }).click();
  await expect(page.getByRole("heading", { name: "Software developer" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Career roadmap timeline" }).getByText("Recommended next")).toBeVisible();
  await page.getByRole("button", { name: "Study recommended lesson" }).click();
  await expect(page.getByRole("dialog").getByText("A short catalog lesson.")).toBeVisible();
  await page.getByRole("button", { name: "Close lesson" }).click();
  await page.getByRole("button", { name: "Complete milestone" }).click();
  await expect(page.getByRole("button", { name: "Milestone completed" })).toBeDisabled();
  await expect(page.getByText("100%")).toBeVisible();
});
