export const voiceNavigationDestinations = [
  { path: "/dashboard", label: "Dashboard", commands: ["open dashboard", "go to dashboard", "show dashboard", "డాష్‌బోర్డ్ తెరువు", "డాష్ బోర్డ్ తెరువు"] },
  { path: "/classroom", label: "AI Classroom", commands: ["open classroom", "go to classroom", "start classroom", "start ai classroom", "క్లాస్‌రూమ్ తెరువు", "క్లాస్ రూమ్ తెరువు"] },
  { path: "/documents", label: "My Documents", commands: ["open my documents", "go to documents", "show my documents", "open my uploaded pdf", "నా పత్రాలు తెరువు"] },
  { path: "/quizzes", label: "Quizzes", commands: ["open quizzes", "go to quizzes", "నా క్విజ్‌లు తెరువు"] },
  { path: "/progress-analytics", label: "My Progress", commands: ["open my progress", "show my progress", "go to progress", "నా పురోగతి చూపించు"] },
  { path: "/career", label: "Career Advisor", commands: ["open career advisor", "go to career advisor", "open career", "go to future advisor", "open future advisor", "కెరీర్ సలహాదారు తెరువు"] },
  { path: "/assistant", label: "Assistant", commands: ["open assistant", "go to assistant", "assistant open చేయి"] },
  { path: "/research", label: "Research", commands: ["open research", "go to research", "రీసెర్చ్ తెరువు"] },
  { path: "/visual", label: "Visual Learning", commands: ["open visual learning", "go to visual learning", "విజువల్ లెర్నింగ్ తెరువు"] },
  { path: "__back__", label: "Previous page", commands: ["go back", "back", "వెనక్కి వెళ్ళు"] },
];
function normalizeCommand(text) {
  return text.normalize("NFC").toLocaleLowerCase().replace(/[.,!?;:।]+/g, " ").replace(/\s+/g, " ").trim();
}
// Exact allowlist only. The UI must ask the student to confirm before navigating.
export function matchVoiceNavigationCommand(text) {
  const normalized = normalizeCommand(text);
  if (!normalized) return null;
  for (const destination of voiceNavigationDestinations) {
    if (destination.commands.some(command => normalizeCommand(command) === normalized)) return { label: destination.label, path: destination.path };
  }
  return null;
}
