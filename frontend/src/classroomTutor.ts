import type { LearningLanguage, LearningLevel } from "./sessionContext";

export type ClassroomTutorRequest = {
  sessionId: string;
  question: string;
  language: LearningLanguage;
  learningLevel: LearningLevel;
};

export type ClassroomTutorTransport = (sessionId: string, message: string) => Promise<{ reply: string }>;

/** Keeps the original doubt and learner settings explicit at the classroom tutor boundary. */
export function generateClassroomExplanation(input: ClassroomTutorRequest, send: ClassroomTutorTransport): Promise<{ reply: string }> {
  if (!input.sessionId.trim() || !input.question.trim()) throw new Error("A saved session and student doubt are required.");
  const message = [
    "In the interactive classroom, explain this student doubt clearly with a short step-by-step lesson, one useful example, and a brief check for understanding.",
    `Original doubt: ${input.question}`,
    `Teaching context: language=${input.language}, level=${input.learningLevel}.`,
  ].join("\n");
  return send(input.sessionId, message);
}
