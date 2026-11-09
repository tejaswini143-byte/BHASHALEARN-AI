export function clampMastery(value: number): number {
  return Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : 0;
}

export function formatSessionDate(value: string): string {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "Date unavailable";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function firstName(displayName: string): string {
  return displayName.trim().split(/\s+/)[0] || "there";
}

export function matchesSession(topic: string, query: string): boolean {
  return topic.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase());
}
