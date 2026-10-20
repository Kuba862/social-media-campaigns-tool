import { expect, test } from "@playwright/test";
import { ensureTestUser, signIn } from "./helpers";

test.beforeAll(async ({ playwright }) => {
  const api = await playwright.request.newContext();
  await ensureTestUser(api);
  await api.dispose();
});

test("draft is saved and submit reports Meta is not configured", async ({ page }) => {
  await signIn(page);
  await page.getByRole("link", { name: "Templates" }).click();
  await expect(page.getByRole("heading", { name: "Templates" })).toBeVisible();

  const name = `e2e_${Date.now()}`;
  await page.getByLabel("Name", { exact: true }).fill(name);
  await page.getByLabel("Body", { exact: true }).fill("Cześć {{1}}!");
  await page.getByLabel("Example values").fill("Ala");
  await page.getByRole("button", { name: "Save draft" }).click();

  const row = page.getByRole("row").filter({ hasText: name });
  await expect(row).toContainText("DRAFT");
  await row.getByRole("button", { name: "Submit" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Meta" })).toContainText(
    "Meta is not configured",
  );
});
