export type Student = { id: string; email: string; display_name: string };
export type AuthResult = { access_token: string; token_type: string };
const API = "/api/v1";
const TOKEN_KEY = "bhashalearn_access_token";

export function getToken(): string | null { return sessionStorage.getItem(TOKEN_KEY); }
export function saveToken(token: string): void { sessionStorage.setItem(TOKEN_KEY, token); }
export function clearToken(): void { sessionStorage.removeItem(TOKEN_KEY); }

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); this.name = "ApiError"; }
}
function describeError(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map(item => typeof item?.msg === "string" ? item.msg : "Invalid field").join("; ");
  if (detail && typeof detail === "object" && "message" in detail && typeof detail.message === "string") return detail.message;
  return "Request failed. Please try again.";
}
export function requestHeaders(options: RequestInit = {}): HeadersInit {
  const isForm = typeof FormData !== "undefined" && options.body instanceof FormData;
  return { ...(isForm ? {} : { "Content-Type": "application/json" }), ...options.headers };
}
export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(API + path, {
      ...options,
      headers: requestHeaders(options),
    });
  } catch {
    throw new ApiError(0, "Cannot connect to the backend. Check that the configured FastAPI service is running and try again.");
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body && typeof body === "object" && "detail" in body ? body.detail : null;
    throw new ApiError(response.status, describeError(detail));
  }
  return body as T;
}
export function registerStudent(email: string, display_name: string, password: string): Promise<Student> {
  return request<Student>("/auth/register", { method: "POST", body: JSON.stringify({ email, display_name, password }) });
}
export function loginStudent(email: string, password: string): Promise<AuthResult> {
  return request<AuthResult>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
}
export function getCurrentStudent(token: string): Promise<Student> {
  return request<Student>("/auth/me", { headers: { Authorization: "Bearer " + token } });
}
