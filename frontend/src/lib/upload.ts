import { refreshAccess } from "@/api/client";
import { useAuth } from "@/features/auth/store";

export type UploadHandle = { promise: Promise<unknown>; cancel: () => void };

export class UploadError extends Error {
  constructor(
    message: string,
    readonly fields: Record<string, string[]> = {},
  ) {
    super(message);
  }
}

function attempt(
  url: string,
  form: FormData,
  token: string | null,
  onProgress: (pct: number) => void,
  signal: AbortSignal,
) {
  return new Promise<{ status: number; body: unknown }>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.withCredentials = true;
    xhr.timeout = 120_000;
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress((event.loaded / event.total) * 100);
    };
    xhr.onload = () => {
      resolve({ status: xhr.status, body: parseJson(xhr.responseText) });
    };
    xhr.onerror = () => reject(new UploadError("Upload failed. Check your connection."));
    xhr.ontimeout = () => reject(new UploadError("The upload took too long."));
    xhr.onabort = () => reject(new DOMException("Upload cancelled", "AbortError"));
    signal.addEventListener("abort", () => xhr.abort());
    xhr.send(form);
  });
}

function parseJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function describe(body: unknown): UploadError {
  if (body && typeof body === "object") {
    const record = body as Record<string, unknown>;
    const fields: Record<string, string[]> = {};
    for (const [key, value] of Object.entries(record)) {
      fields[key] = Array.isArray(value) ? value.map(String) : [String(value)];
    }
    const first = Object.values(fields)[0]?.[0];
    if (first) return new UploadError(first, fields);
  }
  return new UploadError("The server rejected the upload.");
}

export function uploadForm(
  path: string,
  form: FormData,
  onProgress: (pct: number) => void,
): UploadHandle {
  const controller = new AbortController();
  const base = import.meta.env.VITE_API_URL ?? window.location.origin;
  const url = `${base}${path}`;
  const promise = (async () => {
    let result = await attempt(url, form, useAuth.getState().access, onProgress, controller.signal);
    if (result.status === 401) {
      const refreshed = await refreshAccess();
      if (refreshed === "offline") throw new UploadError("Can't reach the server. Try again.");
      if (refreshed === "expired") {
        useAuth.getState().expire();
        throw new UploadError("Your session expired. Sign in again.");
      }
      result = await attempt(url, form, useAuth.getState().access, onProgress, controller.signal);
    }
    if (result.status >= 400) throw describe(result.body);
    return result.body;
  })();
  return { promise, cancel: () => controller.abort() };
}
