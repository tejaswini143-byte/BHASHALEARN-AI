export type TeachingDifficulty = "beginner" | "intermediate" | "advanced";
export type TeachingLanguage = "telugu" | "english" | "mixed";
export type PersonalizedLessonPlan = {
  learning_objective: string;
  prerequisite_concepts: string[];
  explanation_strategy: string;
  examples: string[];
  understanding_checks: string[];
  suggested_next_activity: string;
  difficulty: TeachingDifficulty;
  language: TeachingLanguage;
  recommended_topic: string | null;
  recommendation_reason: string;
  fallback: boolean;
  grounded: boolean;
};
export type PersonalizedLessonResponse = {
  session_id: string;
  plan: PersonalizedLessonPlan;
  evidence_attempts: number;
  mastery_score: number | null;
  recommendation_source: "recorded_practice" | "no_history";
  learning_goal: string | null;
  citations: Array<{ citation_id: string; document_id: string; document_title: string; page_number: number }>;
};

export function validatePersonalizedLesson(value: unknown): PersonalizedLessonResponse {
  if (!value || typeof value !== "object") throw new Error("Lesson plan response is unavailable.");
  const response = value as Partial<PersonalizedLessonResponse>;
  const plan = response.plan;
  if (typeof response.session_id !== "string" || !Number.isFinite(response.evidence_attempts) || (response.evidence_attempts ?? -1) < 0
      || (response.mastery_score !== null && (typeof response.mastery_score !== "number" || !Number.isFinite(response.mastery_score)))
      || !["recorded_practice", "no_history"].includes(String(response.recommendation_source))
      || (response.learning_goal !== null && typeof response.learning_goal !== "string")
      || !plan || typeof plan !== "object"
      || typeof plan.learning_objective !== "string" || !Array.isArray(plan.prerequisite_concepts)
      || typeof plan.explanation_strategy !== "string" || !Array.isArray(plan.examples) || !plan.examples.length
      || !Array.isArray(plan.understanding_checks) || !plan.understanding_checks.length
      || typeof plan.suggested_next_activity !== "string"
      || !["beginner", "intermediate", "advanced"].includes(plan.difficulty)
      || !["telugu", "english", "mixed"].includes(plan.language)
      || typeof plan.recommendation_reason !== "string" || typeof plan.fallback !== "boolean"
      || typeof plan.grounded !== "boolean" || !Array.isArray(response.citations)) {
    throw new Error("Lesson plan response did not pass validation.");
  }
  return value as PersonalizedLessonResponse;
}

export function isExplicitConfusion(text: string): boolean {
  const normalized = text.toLocaleLowerCase();
  return ["i don't understand", "i do not understand", "i'm confused", "i am confused", "explain again", "i'm lost", "ardham kaledu"]
    .some(signal => normalized.includes(signal));
}
