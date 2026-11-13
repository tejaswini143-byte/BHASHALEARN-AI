import type { BilingualText, VisualLesson, VisualLessonId } from "./visualLessonsModel";

export type VisualLessonLanguage = keyof BilingualText;
export type VisualLessonSceneKind = "solar-system" | "geometry" | "pendulum";
export type VisualLessonEnvelope = {
  version: 1;
  lesson: VisualLesson;
  scene: { kind: VisualLessonSceneKind };
};

const validIds = new Set<VisualLessonId>(["solar-system", "geometry", "pendulum"]);
const hasText = (value: unknown): value is BilingualText =>
  typeof value === "object" && value !== null &&
  typeof (value as BilingualText).en === "string" && Boolean((value as BilingualText).en.trim()) &&
  typeof (value as BilingualText).te === "string" && Boolean((value as BilingualText).te.trim());

export function validateVisualLessonEnvelope(value: unknown): VisualLessonEnvelope {
  if (!value || typeof value !== "object") throw new Error("Visual lesson envelope must be an object.");
  const candidate = value as Partial<VisualLessonEnvelope>;
  if (candidate.version !== 1) throw new Error("Unsupported visual lesson contract version.");
  const lesson = candidate.lesson;
  if (!lesson || !validIds.has(lesson.id)) throw new Error("Unsupported visual lesson id.");
  if (!candidate.scene || candidate.scene.kind !== lesson.id) throw new Error("Visual lesson scene does not match its id.");
  if (![lesson.title, lesson.subject, lesson.topic, lesson.description].every(hasText)) throw new Error("Visual lesson bilingual metadata is invalid.");
  if (!Array.isArray(lesson.objectives) || !lesson.objectives.length || !lesson.objectives.every(hasText)) throw new Error("Visual lesson objectives are invalid.");
  if (!Array.isArray(lesson.takeaways) || !lesson.takeaways.length || !lesson.takeaways.every(hasText)) throw new Error("Visual lesson takeaways are invalid.");
  if (!Array.isArray(lesson.steps) || !lesson.steps.length || !lesson.steps.every(step => step && hasText(step.title) && hasText(step.explanation))) throw new Error("Visual lesson steps are invalid.");
  return candidate as VisualLessonEnvelope;
}

export function createVisualLessonEnvelope(lesson: VisualLesson): VisualLessonEnvelope {
  return validateVisualLessonEnvelope({ version: 1, lesson, scene: { kind: lesson.id } });
}
