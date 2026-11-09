export function isEducationalDoubt(value: string): boolean {
  const text = value.trim();
  if (text.length < 8) return false;
  return /\?|\b(explain|how|why|what|when|where|solve|derive|meaning|difference|help|understand|learn|calculate)\b/i.test(text) || /[\u0C00-\u0C7F]/.test(text);
}

export function classroomUrl(sessionId: string, question: string, mode?: "realistic" | "holographic"): string {
  const params = new URLSearchParams({ session: sessionId, question });
  if (mode) params.set("mode", mode);
  return `/teacher?${params.toString()}`;
}
