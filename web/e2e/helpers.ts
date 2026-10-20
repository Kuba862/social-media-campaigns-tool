import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const EMAIL = "ala@example.org";
export const PASSWORD = "lokalne-haslo-123";

/** Creates the test user through Supabase Auth; 422 means it already exists. */
export async function ensureTestUser(api: APIRequestContext): Promise<void> {
  const response = await api.post(`${process.env.NEXT_PUBLIC_SUPABASE_URL}/auth/v1/signup`, {
    headers: { apikey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "" },
    data: { email: EMAIL, password: PASSWORD },
  });
  expect([200, 422]).toContain(response.status());
}

export async function signIn(page: Page): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("E-mail").fill(EMAIL);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText(`Signed in as ${EMAIL}`)).toBeVisible();
}
