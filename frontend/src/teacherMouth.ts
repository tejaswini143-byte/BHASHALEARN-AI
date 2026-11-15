/** Conservative mapping of teacher visemes to common ARKit / glTF morph targets.
 * Only speech-related morphs are touched. Expressions remain independent.
 */
export type TeacherViseme = "sil" | "aa" | "ee" | "oh" | "mm" | "fv" | "th";

export function speechMorphWeight(name: string, viseme: TeacherViseme): number | null {
  const key = name.toLowerCase().replace(/[^a-z0-9]/g, "");
  const aliases: Record<Exclude<TeacherViseme, "sil">, string[]> = {
    aa: ["visemeaa", "visemea", "mouthopen", "jawopen", "aa"],
    ee: ["visemeee", "visemee", "mouthsmileleft", "mouthsmileright", "ee"],
    oh: ["visemeoh", "visemeo", "mouthfunnel", "mouthpucker", "oh"],
    mm: ["visememm", "visemem", "mouthclose", "mm"],
    fv: ["visemefv", "visemef", "mouthpressleft", "mouthpressright", "fv"],
    th: ["visemeth", "visemeth", "tongueout", "th"],
  };
  const known = Object.values(aliases).flat();
  if (!known.includes(key)) return null;
  if (viseme === "sil") return 0;
  return aliases[viseme].includes(key) ? 0.55 : 0;
}
