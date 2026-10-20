import { expect, test } from "@playwright/test";

const EMAIL = "ala@example.org";
const PASSWORD = "lokalne-haslo-123";

test.beforeAll(async ({ playwright }) => {
  const api = await playwright.request.newContext();
  const response = await api.post(`${process.env.NEXT_PUBLIC_SUPABASE_URL}/auth/v1/signup`, {
    headers: { apikey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "" },
    data: { email: EMAIL, password: PASSWORD },
  });
  expect([200, 422]).toContain(response.status());
  await api.dispose();
});

test("anonymous visitor is sent to the login page", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
});

test("allowed user signs in and out", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("E-mail").fill(EMAIL);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText(`Signed in as ${EMAIL}`)).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);
});

test("other domain is rejected before Supabase is asked", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("E-mail").fill("ola@evil.com");
  await page.getByLabel("Password").fill("whatever");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "domain" })).toHaveText(
    "This e-mail domain is not allowed.",
  );
});
