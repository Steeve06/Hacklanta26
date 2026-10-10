import createClient from "openapi-fetch";
import type { paths } from "./schema";
import { useAuth } from "@/features/auth/store";

const API_BASE = import.meta.env.VITE_API_URL ?? window.location.origin;
const REQUEST_TIMEOUT_MS = 20_000;

let refreshing: Promise<string | null> | null = null;

export async function refreshAccess(): Promise<string | null> {
  refreshing ??= (async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: { "X-Requested-With": "pulse" },
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });
      if (!res.ok) return null;
      const body = (await res.json()) as { access: string };
      useAuth.getState().setAccess(body.access);
      return body.access;
    } catch {
      return null;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

async function send(request: Request, token: string | null): Promise<Response> {
  const headers = new Headers(request.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  headers.set("X-Requested-With", "pulse");
  return fetch(new Request(request, { headers, credentials: "include" }), {
    signal: AbortSignal.any([request.signal, AbortSignal.timeout(REQUEST_TIMEOUT_MS)]),
  });
}

export async function authFetch(input: Request): Promise<Response> {
  const retryCopy = input.clone();
  const response = await send(input, useAuth.getState().access);
  if (response.status !== 401 || input.url.includes("/auth/")) return response;
  const fresh = await refreshAccess();
  if (!fresh) {
    useAuth.getState().expire();
    return response;
  }
  return send(retryCopy, fresh);
}

export const api = createClient<paths>({ baseUrl: API_BASE, fetch: authFetch });

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly fields: Record<string, string[]> = {},
  ) {
    super(message);
  }
}

/** True for a 404 or 403: retrying won't help, so show "not found" instead of an error. */
export function isMissing(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 404 || error.status === 403);
}

function messageFrom(error: unknown): { message: string; fields: Record<string, string[]> } {
  if (error && typeof error === "object") {
    const record = error as Record<string, unknown>;
    if (typeof record.detail === "string") return { message: record.detail, fields: {} };
    const fields: Record<string, string[]> = {};
    for (const [key, value] of Object.entries(record)) {
      if (Array.isArray(value)) fields[key] = value.map(String);
      else if (typeof value === "string") fields[key] = [value];
    }
    const first = fields.non_field_errors?.[0] ?? Object.values(fields)[0]?.[0];
    if (first) return { message: first, fields };
  }
  return { message: "Something went wrong. Try again.", fields: {} };
}

export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || !result.response.ok) {
    const { message, fields } = messageFrom(result.error);
    throw new ApiError(message, result.response.status, fields);
  }
  return result.data as T;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof DOMException && error.name === "TimeoutError")
    return "The server took too long to respond.";
  if (error instanceof TypeError) return "Can't reach the server. Check your connection.";
  return "Something went wrong. Try again.";
}
