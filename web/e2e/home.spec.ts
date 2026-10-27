import { expect, test } from "@playwright/test";
import { ensureTestUser, signIn } from "./helpers";

test.beforeAll(async ({ playwright }) => {
  const api = await playwright.request.newContext();
  await ensureTestUser(api);
  await api.dispose();
});

test("the home page shows the four campaign data boxes", async ({ page }) => {
  await signIn(page);
  for (const title of ["Messages", "Journeys", "Templates", "Sync"]) {
    const box = page.getByRole("region", { name: title, exact: true });
    await expect(box).toBeVisible();
    // Either a chart with its table twin or the empty state; never an API error.
    await expect(box.getByRole("alert")).toHaveCount(0);
    await expect(box.getByRole("img").or(box.getByText("No data yet."))).toBeVisible();
  }
});
