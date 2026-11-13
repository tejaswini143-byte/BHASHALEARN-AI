import { ApiError, getToken, request } from "./auth";
import { buildFutureSeekerHandoff, type FutureSeekerHandoff } from "./futureSeekerContract";

export type SavedFutureSeekerReflection = FutureSeekerHandoff & {
  id: string;
  createdAt: string;
};

export async function saveFutureSeekerReflection(
  careerId: FutureSeekerHandoff["careerId"],
  completedSteps: number,
  skills: string[],
): Promise<SavedFutureSeekerReflection> {
  const token = getToken();
  if (!token) throw new Error("Sign in to save this reflection.");
  const payload = buildFutureSeekerHandoff(careerId, completedSteps, skills);
  const result = await request<SavedFutureSeekerReflection>("/future-seeker/reflections", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
  if (!result || typeof result.id !== "string" || result.source !== "illustrative-simulation") {
    throw new Error("Unexpected reflection response.");
  }
  return result;
}

export function describeFutureSeekerError(error: unknown): string {
  if (error instanceof ApiError && error.status === 401) return "Your session expired. Sign in again to save.";
  if (error instanceof Error && error.message === "Sign in to save this reflection.") return error.message;
  return "Could not save the reflection. Please try again.";
}

export async function listFutureSeekerReflections(): Promise<SavedFutureSeekerReflection[]> {
  const token = getToken();
  if (!token) throw new Error("Sign in to view saved reflections.");
  const items = await request<unknown>("/future-seeker/reflections", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!Array.isArray(items) || items.length > 100 ||
      !items.every(item => item && typeof item === "object" &&
        typeof item.id === "string" && typeof item.createdAt === "string" &&
        item.source === "illustrative-simulation")) {
    throw new Error("Invalid saved reflections response.");
  }
  return items as SavedFutureSeekerReflection[];
}

export async function deleteFutureSeekerReflection(id: string): Promise<void> {
  const token = getToken();
  if (!token) throw new Error("Sign in to delete saved reflections.");
  if (!/^[0-9a-f-]{36}$/i.test(id)) throw new Error("Invalid reflection identifier.");
  await request<void>(`/future-seeker/reflections/${encodeURIComponent(id)}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
}
