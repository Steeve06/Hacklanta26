import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const PASSWORD = "pulse-demo";

export async function signIn(page: Page, email: string): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/(pulse|lms|demo)/);
}

/** A small authenticated client for checking what the server recorded. */
export async function apiAs(request: APIRequestContext, email: string) {
  const login = await request.post("/api/v1/auth/login", {
    data: { email, password: PASSWORD },
  });
  expect(login.ok()).toBeTruthy();
  const { access } = (await login.json()) as { access: string };
  const headers = { Authorization: `Bearer ${access}` };
  return {
    get: async <T>(path: string): Promise<T> => {
      const res = await request.get(path, { headers });
      expect(res.ok(), `GET ${path}`).toBeTruthy();
      return (await res.json()) as T;
    },
    post: (path: string, data?: unknown) => request.post(path, { headers, data }),
  };
}
