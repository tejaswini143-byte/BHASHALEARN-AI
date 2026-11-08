export type CareerPhase = {
  id: string; skill_key: string; title: string; title_te: string; position: number;
  prerequisite_skills: string[]; course_id: string | null; course_title: string | null;
  lesson_id: string | null; lesson_title: string | null; practice: string; practice_te: string;
  assessment: string; assessment_topic: string | null; project: string; milestone_description: string; milestone_description_te: string;
  estimated_hours: number; milestone_id: string; completed: boolean;
};
export type CareerRoadmap = {
  goal_id: string; career_key: string; career_title: string; summary: string; summary_te: string;
  language: "english" | "telugu" | "mixed"; phases: CareerPhase[];
  weekly_plan: { day: string; minutes: number; activity: string }[];
  total_estimated_hours: number; planner: string;
  skill_gaps: { skill_key: string; name: string; status: string; self_assessed_proficiency: string | null; verified: boolean }[];
  progress: { completed_milestones: number; total_milestones: number };
};
export const percentComplete = (roadmap: CareerRoadmap) => roadmap.progress.total_milestones
  ? Math.min(100, Math.max(0, Math.round(100 * roadmap.progress.completed_milestones / roadmap.progress.total_milestones))) : 100;
export const gapLabel = (status: string, language: string) => {
  const en: Record<string, string> = { already_demonstrated: "Demonstrated", self_reported: "Self-reported", needs_assessment: "Needs assessment", recommended_next: "Recommended next", not_started: "Not started" };
  const te: Record<string, string> = { already_demonstrated: "నైపుణ్యం ప్రదర్శించారు", self_reported: "స్వీయ అంచనా", needs_assessment: "అంచనా అవసరం", recommended_next: "తదుపరి సిఫార్సు", not_started: "ప్రారంభించలేదు" };
  if (language === "telugu") return te[status] ?? status;
  if (language === "mixed") return `${en[status] ?? status} · ${te[status] ?? status}`;
  return en[status] ?? status;
};
