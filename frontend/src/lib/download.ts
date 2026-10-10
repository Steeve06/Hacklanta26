import { authFetch } from "@/api/client";

export async function downloadFile(path: string, filename: string): Promise<void> {
  const base = import.meta.env.VITE_API_URL ?? window.location.origin;
  const response = await authFetch(new Request(`${base}${path}`));
  if (!response.ok) throw new Error("Download failed.");
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
