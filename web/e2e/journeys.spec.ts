import { expect, test } from "@playwright/test";
import { ensureTestUser, signIn } from "./helpers";

test.beforeAll(async ({ playwright }) => {
  const api = await playwright.request.newContext();
  await ensureTestUser(api);
  await api.dispose();
});

test("a new journey opens its page and is listed without versions", async ({ page }) => {
  await signIn(page);
  await page.getByRole("navigation").getByRole("link", { name: "Journeys" }).click();
  await expect(page.getByRole("heading", { name: "Journeys" })).toBeVisible();

  const name = `e2e journey ${Date.now()}`;
  await page.getByLabel("Name", { exact: true }).fill(name);
  await page.getByRole("button", { name: "Create" }).click();
  await expect(page.getByRole("heading", { name })).toBeVisible(); // redirected to the journey
  await expect(page.getByText("No versions yet.")).toBeVisible();

  await page.getByRole("navigation").getByRole("link", { name: "Journeys" }).click();
  const row = page.getByRole("row").filter({ hasText: name });
  await expect(row).toContainText("draft");
  await expect(row).toContainText("no versions");
});
