import { expect, test } from "@playwright/test";
import { ensureTestUser, signIn } from "./helpers";

test.beforeAll(async ({ playwright }) => {
  const api = await playwright.request.newContext();
  await ensureTestUser(api);
  await api.dispose();
});

test("the editor adds a node and saves it as the draft", async ({ page }) => {
  await signIn(page);
  await page.goto("/journeys");
  const name = `e2e editor ${Date.now()}`;
  await page.getByLabel("Name", { exact: true }).fill(name);
  await page.getByRole("button", { name: "Create" }).click();
  await page.getByRole("link", { name: "Edit", exact: true }).click();
  await expect(page.getByRole("heading", { name: `Edit: ${name}` })).toBeVisible();
  await expect(page.locator(".react-flow__node")).toHaveCount(2); // start and end

  await page.getByRole("button", { name: "Add wait", exact: true }).click();
  await expect(page.locator(".react-flow__node")).toHaveCount(3);
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByRole("status")).toHaveText("Draft v1 saved");

  await page.getByRole("link", { name, exact: true }).click();
  const row = page.getByRole("row").filter({ hasText: "draft" });
  await expect(row).toContainText("3"); // nodes
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
});
