/**
 * Feature 3 / Phase 1: a deliberately small boundary between the existing
 * deterministic Future Me simulation and the authenticated career roadmap.
 * Simulation choices are reflective evidence, never verified competencies.
 */
export type FutureSeekerHandoff = {
  version: 1;
  careerId: "software-engineer" | "doctor" | "scientist" | "entrepreneur";
  completedSteps: number;
  observedSkills: string[];
  source: "illustrative-simulation";
};

const CAREERS = new Set(["software-engineer", "doctor", "scientist", "entrepreneur"]);
const MAX_SKILLS = 24;
export function validateFutureSeekerHandoff(value: unknown): FutureSeekerHandoff {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Invalid Future Seeker handoff");
  const data = value as Record<string, unknown>;
  if (data.version !== 1 || data.source !== "illustrative-simulation" ||
      typeof data.careerId !== "string" || !CAREERS.has(data.careerId) ||
      !Number.isInteger(data.completedSteps) || (data.completedSteps as number) < 0 || (data.completedSteps as number) > 20 ||
      !Array.isArray(data.observedSkills) || data.observedSkills.length > MAX_SKILLS ||
      !data.observedSkills.every(skill => typeof skill === "string" && skill.length > 0 && skill.length <= 80) ||
      new Set(data.observedSkills).size !== data.observedSkills.length) {
    throw new Error("Invalid Future Seeker handoff");
  }
  return data as FutureSeekerHandoff;
}

export function buildFutureSeekerHandoff(careerId: FutureSeekerHandoff["careerId"], completedSteps: number, skills: string[]): FutureSeekerHandoff {
  return validateFutureSeekerHandoff({
    version: 1,
    careerId,
    completedSteps,
    observedSkills: [...new Set(skills)],
    source: "illustrative-simulation",
  });
}
