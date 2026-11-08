export type LearningLanguage = "english" | "telugu" | "mixed";
export type LearningLevel = "beginner" | "intermediate" | "advanced";
export type LearningPace = "slow" | "steady" | "fast";

export type LearningPreferences = {
  preferred_language: LearningLanguage;
  learning_level: LearningLevel;
  learning_pace: LearningPace;
  learning_goal: string | null;
};

export const DEFAULT_LEARNING_PREFERENCES: LearningPreferences = {
  preferred_language: "mixed", learning_level: "beginner", learning_pace: "steady", learning_goal: null,
};

export function mergeLearningPreferences(current: LearningPreferences, patch: Partial<LearningPreferences>): LearningPreferences {
  return { ...current, ...patch };
}

export type LearningProfile = {
  preferred_language: LearningLanguage;
  learning_pace: LearningPace;
  proficiencies: Array<{
    subject: string | null; topic: string; mastery_score: number; evidence_attempts: number;
    difficulty: LearningLevel; strategy: string; recommendation: string; revision_recommended: boolean;
    last_activity_at: string | null;
  }>;
  recent_activity: Array<{ topic: string; outcome: "correct" | "incorrect"; occurred_at: string }>;
  revision_topics: string[];
};
