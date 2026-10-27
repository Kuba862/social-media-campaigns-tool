import { expect, test } from "@playwright/test";
import { createDraft, ensureTestUser, signIn } from "./helpers";

test.beforeAll(async ({ playwright }) => {
  const api = await playwright.request.newContext();
  await ensureTestUser(api);
  await api.dispose();
});

test("draft is saved and submit reports Meta is not configured", async ({ page }) => {
  await signIn(page);
  await page.getByRole("navigation").getByRole("link", { name: "Templates" }).click();
  await expect(page.getByRole("heading", { name: "Templates" })).toBeVisible();
  await page.getByRole("link", { name: "New message" }).click();
  await expect(page.getByRole("heading", { name: "New message" })).toBeVisible();

  const name = await createDraft(page);
  const row = page.getByRole("row").filter({ hasText: name });
  await expect(row).toContainText("DRAFT");
  await row.getByRole("button", { name: "Submit" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Meta" })).toContainText(
    "Meta is not configured",
  );

  page.once("dialog", (dialog) => dialog.accept());
  await row.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByRole("row").filter({ hasText: name })).toHaveCount(0);
});
