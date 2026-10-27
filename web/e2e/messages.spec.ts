import { expect, test } from "@playwright/test";
import { approveTemplate, createDraft, ensureTestUser, signIn } from "./helpers";

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
  const name = await createDraft(page);
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
  // Without Meta the test send above stores nothing, so the log may be empty on a fresh
  // database; with rows (a worker or a configured Meta wrote them) a click opens the raw JSON.
  const logRows = page.locator("tbody tr.expandable");
  if ((await logRows.count()) === 0) {
    await expect(page.getByText("No messages yet.")).toBeVisible();
  } else {
    await logRows.first().click();
    await expect(page.getByLabel("Meta JSON", { exact: true })).toContainText('"send_response"');
  }
});
