import { ApiError, getToken, request } from "./auth";

export type LearningMemory = { id: string; topic: string; note: string; created_at: string };
export type MemoryInput = { topic: string; note: string };

function authenticated<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  if (!token) throw new ApiError(401, "Your session has expired. Please sign in again.");
  return request<T>(path, {
    ...options,
    headers: { ...options.headers, Authorization: `Bearer ${token}` },
  });
}

export const listMemories = () => authenticated<LearningMemory[]>("/memories");
export const createMemory = (value: MemoryInput) => authenticated<LearningMemory>("/memories", {
  method: "POST", body: JSON.stringify(value),
});
export const updateMemory = (id: string, value: MemoryInput) => authenticated<LearningMemory>(`/memories/${encodeURIComponent(id)}`, {
  method: "PATCH", body: JSON.stringify(value),
});
export const deleteMemory = (id: string) => authenticated<void>(`/memories/${encodeURIComponent(id)}`, { method: "DELETE" });
