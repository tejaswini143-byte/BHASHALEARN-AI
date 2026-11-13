import { expect, test } from "@playwright/test";

const phase = (completed = false, lesson_completed = false) => ({
  id: "software-developer-digital-literacy", skill_key: "digital-literacy", title: "Digital literacy", title_te: "డిజిటల్ అక్షరాస్యత",
  position: 1, prerequisite_skills: [], course_id: "course-1", course_title: "Digital literacy basics", lesson_id: "lesson-1", lesson_title: "Getting started",
  practice: "Complete a digital literacy practice task.", practice_te: "డిజిటల్ అక్షరాస్యత సాధన పనిని పూర్తి చేయండి.",
  assessment: "Check your understanding of Digital literacy.", assessment_topic: null, project: "Add a digital literacy example to a portfolio project.",
  milestone_description: "Complete the Digital literacy learning and practice steps.", milestone_description_te: "డిజిటల్ అక్షరాస్యత అభ్యాసం మరియు సాధన దశలను పూర్తి చేయండి.",
  estimated_hours: 4, milestone_id: "software-developer-digital-literacy-complete", completed, lesson_completed,
  resources: [{ title: "Getting started", url: "https://docs.python.org/3/tutorial/", kind: "official documentation", free: true }],
});
const roadmap = (completed = false, lessonCompleted = false) => ({
  goal_id: "goal-1", career_key: "software-developer", career_title: "Software developer", summary: "A general learning path. Not a real-time employment forecast.",
  summary_te: "మీ లక్ష్యానికి అనుగుణమైన అభ్యాస మార్గం.", language: "mixed", phases: [phase(completed, lessonCompleted)], weekly_plan: [{ day: "Monday", minutes: 60, activity: "Learn" }],
  total_estimated_hours: 4, planner: "deterministic_catalog_fallback", version_number: 1, estimated_weeks: 1,
  available_minutes_per_day: 120, scheduled_weekly_minutes: 60, target_timeframe_weeks: 24, timeframe_feasibility: "within_target",
  skill_gaps: [{ skill_key: "digital-literacy", name: "Digital literacy", status: "recommended_next", self_assessed_proficiency: null, verified: false }],
  progress: { completed_milestones: completed ? 1 : 0, total_milestones: 1, completed_lessons: lessonCompleted ? 1 : 0 },
  study_adjustment: { state: "not_recorded", previous_target_minutes: null, previous_studied_minutes: null, recommended_weekly_minutes: 300, current_week_start: "2026-11-02", current_week_studied_minutes: 0 },
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
      { career_key: "ai-engineer", title: "AI engineer", required_skills: ["python", "machine-learning"] },
      { career_key: "custom", title: "Custom learning goal", required_skills: ["digital-literacy"] },
    ] };
    else if (url.pathname.endsWith("/skills")) body = { skills: { "digital-literacy": { name: "Digital literacy", prerequisites: [] } }, profile: [] };
    else if (url.pathname.endsWith("/goals") && method === "GET") body = [];
    else if (url.pathname.endsWith("/goals") && method === "POST") body = { id: "goal-1", career_key: "software-developer", career_title: "Software developer", education_level: "beginner", interests: ["apps"], weekly_minutes: 300, preferred_language: "mixed" };
    else if (url.pathname.endsWith("/saved-resources") && method === "GET") body = [];
    else if (url.pathname.endsWith("/saved-resources") && method === "POST") body = { id: "saved-1", resource_url: route.request().postDataJSON().resource_url, title: "Getting started", kind: "official documentation", free: true, created_at: "2026-11-13T00:00:00Z" };
    else if (url.pathname.endsWith("/versions") && method === "GET") body = [{ version_number: 1, change_reason: "generated", created_at: "2026-11-13T00:00:00Z" }];
    else if (url.pathname.endsWith("/analysis") && method === "POST") body = { provider: "gemini", summary_en: "Start with digital foundations and practise each concept.", summary_te: "డిజిటల్ పునాదులతో ప్రారంభించి ప్రతి అంశాన్ని సాధన చేయండి.", disclaimer: "Guidance only.", advice: [{ skill_key: "digital-literacy", priority: 1, estimated_hours: 4, explanation_en: "Build confidence with everyday tools first.", explanation_te: "రోజువారీ డిజిటల్ సాధనాలతో ఆత్మవిశ్వాసం పెంచుకోండి.", next_step_en: "Organize one small project folder.", next_step_te: "ఒక చిన్న ప్రాజెక్ట్ ఫోల్డర్‌ను సర్దండి." }] };
    else if (url.pathname.endsWith("/roadmap") && method === "POST") body = currentPlan;
    else if (url.pathname.endsWith("/replan") && method === "POST") body = currentPlan;
    else if (url.pathname.includes("/milestones/")) { currentPlan = roadmap(true, true); body = currentPlan; }
    else if (url.pathname.includes("/lessons/") && url.pathname.endsWith("/complete")) { currentPlan = roadmap(false, true); body = currentPlan; }
    else if (url.pathname.endsWith("/weekly-progress")) { currentPlan.study_adjustment.current_week_studied_minutes = route.request().postDataJSON().studied_minutes; body = { status: "below_target" }; }
    else if (url.pathname.endsWith("/skills") && method === "PUT") body = { profile: [], evidence_type: "self_reported_only" };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.goto("/career");
  await expect(page.getByRole("heading", { name: "Shape your future with a learning roadmap" })).toBeVisible();
  await page.getByLabel("Software developer", { exact: false }).check();
  await page.getByLabel("Interests").fill("apps");
  await page.getByLabel("Field of study").fill("Computer science");
  await page.getByRole("button", { name: "Create my roadmap" }).click();
  await expect(page.getByRole("heading", { name: "Software developer" })).toBeVisible();
  await expect(page.getByText(/VERSION 1/)).toBeVisible();
  await page.getByRole("button", { name: "Save resource" }).click();
  await expect(page.getByRole("region", { name: "Saved learning resources" })).toContainText("Getting started");
  await page.getByRole("button", { name: "Analyze skill gaps with Gemini" }).click();
  await expect(page.getByRole("region", { name: "Gemini skill gap analysis" })).toContainText("Start with digital foundations");
  await expect(page.getByRole("region", { name: "Career roadmap timeline" }).getByText("Recommended next")).toBeVisible();
  await page.getByRole("button", { name: "Study recommended lesson" }).click();
  await expect(page.getByRole("dialog").getByText("A short catalog lesson.")).toBeVisible();
  await page.getByRole("button", { name: "Mark lesson complete" }).click();
  await expect(page.getByRole("button", { name: "Lesson completed" }).first()).toBeDisabled();
  await page.getByRole("button", { name: "Close lesson" }).click();
  await page.getByRole("button", { name: "Complete milestone" }).click();
  await expect(page.getByRole("button", { name: "Milestone completed" })).toBeDisabled();
  await expect(page.getByText("100%")).toBeVisible();
  await page.getByLabel("Minutes studied this week").fill("45");
  await page.getByRole("button", { name: "Save study time" }).click();
  await expect(page.getByText(/Current log: 45 min/)).toBeVisible();
});
