import type { BilingualText, VisualLesson, VisualLessonId } from "./visualLessonsModel";

export type VisualLessonLanguage = keyof BilingualText;
export type VisualLessonSceneKind = "solar-system" | "geometry" | "pendulum";
export type VisualLessonEnvelope = {
  version: 1;
  lesson: VisualLesson;
  scene: { kind: VisualLessonSceneKind };
};
export type GeneratedVisualLessonEnvelope = {
  version: 2;
  lesson: VisualLesson & {
    questions: { prompt: BilingualText; answer: BilingualText; explanation: BilingualText }[];
    activities: { instruction: BilingualText; control: NonNullable<VisualLesson["activities"]>[number]["control"] }[];
    completion_criteria: BilingualText[];
  };
  scene: { kind: VisualLessonSceneKind; parameters: Record<string, unknown> };
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

export function validateGeneratedVisualLessonEnvelope(value: unknown): GeneratedVisualLessonEnvelope {
  if (!value || typeof value !== "object") throw new Error("Generated lesson must be an object.");
  const candidate = value as Partial<GeneratedVisualLessonEnvelope>;
  if (candidate.version !== 2) throw new Error("Unsupported generated lesson contract version.");
  const lesson = candidate.lesson;
  const scene = candidate.scene;
  if (!lesson || !validIds.has(lesson.id) || !scene || scene.kind !== lesson.id) throw new Error("Generated scene does not match a supported lesson.");
  if (![lesson.title, lesson.subject, lesson.topic, lesson.description].every(hasText)) throw new Error("Generated bilingual metadata is invalid.");
  if (!Array.isArray(lesson.objectives) || !lesson.objectives.length || !lesson.objectives.every(hasText) || !Array.isArray(lesson.takeaways) || !lesson.takeaways.length || !lesson.takeaways.every(hasText)) throw new Error("Generated learning objectives or takeaways are invalid.");
  if (!Array.isArray(lesson.steps) || !lesson.steps.length || !lesson.steps.every(step => step && hasText(step.title) && hasText(step.explanation) && (step.scene_id === undefined || step.scene_id === scene.kind))) throw new Error("Generated lesson steps are invalid.");
  if (!Array.isArray(lesson.questions) || !lesson.questions.length || !lesson.questions.every(item => item && hasText(item.prompt) && hasText(item.answer) && hasText(item.explanation))) throw new Error("Generated questions are invalid.");
  const controls = ["select-planet", "rotate-shape", "adjust-length", "adjust-gravity", "change-time"];
  if (!Array.isArray(lesson.activities) || !lesson.activities.length || !lesson.activities.every(item => item && hasText(item.instruction) && controls.includes(item.control))) throw new Error("Generated activities are invalid.");
  if (!Array.isArray(lesson.completion_criteria) || !lesson.completion_criteria.length || !lesson.completion_criteria.every(hasText)) throw new Error("Generated completion criteria are invalid.");
  const params = scene.parameters;
  if (!params || typeof params !== "object" || Array.isArray(params)) throw new Error("Generated scene parameters are invalid.");
  const keys = Object.keys(params).sort().join(",");
  if (scene.kind === "solar-system" && keys !== "time_scale") throw new Error("Solar-system parameters are invalid.");
  if (scene.kind === "geometry" && keys !== "shape,size") throw new Error("Geometry parameters are invalid.");
  if (scene.kind === "pendulum" && keys !== "gravity,length") throw new Error("Pendulum parameters are invalid.");
  if (scene.kind === "solar-system" && (!Number.isInteger(params.time_scale) || Number(params.time_scale) < 0 || Number(params.time_scale) > 100)) throw new Error("Solar-system time scale is invalid.");
  if (scene.kind === "geometry" && (!(params.shape === "cube" || params.shape === "sphere" || params.shape === "cylinder") || typeof params.size !== "number" || params.size < 0.25 || params.size > 3)) throw new Error("Geometry parameters are invalid.");
  if (scene.kind === "pendulum" && (typeof params.length !== "number" || params.length < 0.5 || params.length > 3 || typeof params.gravity !== "number" || params.gravity < 0.1 || params.gravity > 25)) throw new Error("Pendulum parameters are invalid.");
  return candidate as GeneratedVisualLessonEnvelope;
}
