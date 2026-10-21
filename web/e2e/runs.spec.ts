import { expect, test } from "@playwright/test";
import { ensureTestUser, signIn } from "./helpers";

test.beforeAll(async ({ playwright }) => {
  const api = await playwright.request.newContext();
  await ensureTestUser(api);
  await api.dispose();
});

test("the runs page lists nothing for a new journey and refuses to start an unpublished one", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/journeys");
  const name = `e2e runs ${Date.now()}`;
  await page.getByLabel("Name", { exact: true }).fill(name);
  await page.getByRole("button", { name: "Create" }).click();
  await page.getByRole("link", { name: "Runs", exact: true }).click();
  await expect(page.getByRole("heading", { name: `Runs: ${name}` })).toBeVisible();
  await expect(page.getByText("No runs yet.")).toBeVisible();

  await page.getByLabel("Phone numbers").fill("+48600000009");
  await page.getByRole("button", { name: "Start" }).click();
  // Next's route announcer is also role="alert", so filter by text
  await expect(page.getByRole("alert").filter({ hasText: "published" })).toContainText(
    "no published version",
  );
});
