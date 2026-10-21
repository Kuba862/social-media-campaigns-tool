import { expect, test } from "@playwright/test";
import { approveTemplate, ensureTestUser, signIn } from "./helpers";

test.beforeAll(async ({ playwright }) => {
  const api = await playwright.request.newContext();
  await ensureTestUser(api);
  await api.dispose();
});

test("approved template offers a test send and the log page renders", async ({
  page,
  playwright,
}) => {
  await signIn(page);
  await page.goto("/templates");
  const name = `e2e_${Date.now()}`;
  await page.getByLabel("Name", { exact: true }).fill(name);
  await page.getByLabel("Body", { exact: true }).fill("Cześć {{1}}!");
  await page.getByLabel("Example values").fill("Ala");
  await page.getByRole("button", { name: "Save draft" }).click();
  const row = page.getByRole("row").filter({ hasText: name });
  await expect(row).toContainText("DRAFT");
  await expect(row.getByRole("button", { name: "Send test" })).toHaveCount(0);

  const api = await playwright.request.newContext();
  await approveTemplate(api, name);
  await api.dispose();

  await page.reload();
  await expect(row).toContainText("APPROVED");
  await row.getByPlaceholder("+48...").fill("+48600000001");
  await row.getByRole("button", { name: "Send test" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Meta" })).toContainText(
    "Meta is not configured",
  );

  await page.goto("/messages");
  await expect(page.getByRole("heading", { name: "Messages" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Status" })).toBeVisible();
});
