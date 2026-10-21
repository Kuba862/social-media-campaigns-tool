import { expect, test } from "@playwright/test";
import { ensureTestUser, signIn } from "./helpers";

test.beforeAll(async ({ playwright }) => {
  const api = await playwright.request.newContext();
  await ensureTestUser(api);
  await api.dispose();
});

test("the sync page registers the fake connector and lists it", async ({ page }) => {
  await signIn(page);
  await page.getByRole("navigation").getByRole("link", { name: "Sync" }).click();
  await expect(page.getByRole("heading", { name: "Sync", exact: true })).toBeVisible();

  await page.locator('select[name="name"]').selectOption("fake"); // "Connector" also matches the table label
  await page.getByLabel("Cron (five fields)").fill("30 * * * *");
  await page.getByLabel("Config (JSON, no secrets)").fill('{"default_region": "PL"}');
  await page.getByRole("button", { name: "Save connector" }).click();
  await expect(page.getByRole("status")).toHaveText("fake saved");
  const row = page
    .getByRole("table", { name: "Connectors" })
    .getByRole("row")
    .filter({ hasText: /^fake/ });
  await expect(row).toContainText("30 * * * *");
  await expect(row.getByRole("button", { name: "Run now" })).toBeVisible();

  await page.getByLabel("Config (JSON, no secrets)").fill("{");
  await page.getByRole("button", { name: "Save connector" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "JSON" })).toContainText(
    "config must be valid JSON",
  );
});
