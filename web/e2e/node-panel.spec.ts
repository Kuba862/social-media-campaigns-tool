import { expect, test } from "@playwright/test";
import { ensureTestUser, signIn } from "./helpers";

test.beforeAll(async ({ playwright }) => {
  const api = await playwright.request.newContext();
  await ensureTestUser(api);
  await api.dispose();
});

test("the side panel configures a wait node and wires the path start -> wait -> end", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/journeys");
  const name = `e2e panel ${Date.now()}`;
  await page.getByLabel("Name", { exact: true }).fill(name);
  await page.getByRole("button", { name: "Create" }).click();
  await page.getByRole("link", { name: "Edit", exact: true }).click();
  await page.getByRole("button", { name: "Add wait", exact: true }).click();

  const node = (text: string) => page.locator(".react-flow__node").filter({ hasText: text });
  await node("wait_1").click();
  await expect(page.getByRole("heading", { name: "wait", exact: true })).toBeVisible();
  await page.getByLabel("Amount").fill("2");
  await page.getByLabel("Unit").selectOption("days");
  await page.getByLabel("Next node").selectOption("end");
  await page.getByRole("button", { name: "Apply" }).click();
  await expect(node("wait_1")).toContainText("P2D");
  await expect(page.locator(".react-flow__edge")).toHaveCount(1);

  await node("start").click();
  await expect(page.getByRole("heading", { name: "start", exact: true })).toBeVisible();
  await page.getByLabel("Next node").selectOption("wait_1");
  await page.getByRole("button", { name: "Apply" }).click();
  await expect(page.locator(".react-flow__edge")).toHaveCount(2);

  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByRole("status")).toHaveText("Draft v1 saved");
  await page.reload();
  await expect(node("wait_1")).toContainText("P2D");
  await expect(page.locator(".react-flow__edge")).toHaveCount(2);
});
