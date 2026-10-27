import { expect, test } from "@playwright/test";
import { createServiceMessage, ensureTestUser, signIn } from "./helpers";

test.beforeAll(async ({ playwright }) => {
  const api = await playwright.request.newContext();
  await ensureTestUser(api);
  await api.dispose();
});

test("a journey with a service message publishes", async ({ page }) => {
  await signIn(page);
  await page.goto("/journeys");
  const name = `e2e text ${Date.now()}`;
  await page.getByLabel("Name", { exact: true }).fill(name);
  await page.getByRole("button", { name: "Create" }).click();
  await page.getByRole("link", { name: "Edit", exact: true }).click();
  await page.getByRole("button", { name: "Add send_text", exact: true }).click();
  await expect(page.getByRole("list", { name: "Problems" })).toContainText("write the text");

  const field = (name: string) => page.locator(`select[name="${name}"]`);
  const apply = () => page.getByRole("button", { name: "Apply" }).click();
  const select = async (id: string) => {
    await page.locator(".react-flow__node").filter({ hasText: id }).click();
    await expect(page.getByText(`id: ${id}`, { exact: true })).toBeVisible();
  };
  await select("start");
  await field("next").selectOption("send_text_1");
  await apply();
  await select("send_text_1");
  await page.locator('textarea[name="text"]').fill("Cześć {{contact.first_name}}!");
  await field("if_closed").selectOption("fail");
  await field("next").selectOption("end");
  await apply();

  await expect(page.getByText("Ready to publish.")).toBeVisible();
  await page.getByRole("button", { name: "Publish" }).click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  const row = page.getByRole("row").filter({ hasText: /published/ });
  await expect(row).toHaveCount(1);
  await expect(row).toContainText("3"); // start, send_text, end
});

test("a send_text node can send a saved service message", async ({ page }) => {
  await signIn(page);
  const saved = await createServiceMessage(page);
  await page.goto("/journeys");
  const name = `e2e saved ${Date.now()}`;
  await page.getByLabel("Name", { exact: true }).fill(name);
  await page.getByRole("button", { name: "Create" }).click();
  await page.getByRole("link", { name: "Edit", exact: true }).click();
  await page.getByRole("button", { name: "Add send_text", exact: true }).click();
  await expect(page.getByRole("list", { name: "Problems" })).toContainText(
    "pick a saved service message",
  );

  const field = (name: string) => page.locator(`select[name="${name}"]`);
  const apply = () => page.getByRole("button", { name: "Apply" }).click();
  const select = async (id: string) => {
    await page.locator(".react-flow__node").filter({ hasText: id }).click();
    await expect(page.getByText(`id: ${id}`, { exact: true })).toBeVisible();
  };
  await select("start");
  await field("next").selectOption("send_text_1");
  await apply();
  await select("send_text_1");
  await field("message_id").selectOption({ label: `${saved} (pl)` });
  await expect(page.locator('textarea[name="text"]')).toHaveCount(0); // the saved text is used
  await field("next").selectOption("end");
  await apply();
  await expect(
    page.locator(".react-flow__node").filter({ hasText: "saved message" }),
  ).toBeVisible();
  await expect(page.getByText("Ready to publish.")).toBeVisible();
  await page.getByRole("button", { name: "Publish" }).click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: /published/ })).toHaveCount(1);
});
