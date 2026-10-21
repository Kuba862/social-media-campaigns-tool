import { expect, test } from "@playwright/test";
import { approvedTemplate, ensureTestUser, signIn } from "./helpers";

test.beforeAll(async ({ playwright }) => {
  const api = await playwright.request.newContext();
  await ensureTestUser(api);
  await api.dispose();
});

test("a journey built only in the editor publishes", async ({ page, playwright }) => {
  await signIn(page);
  const api = await playwright.request.newContext();
  const template = await approvedTemplate(page, api);
  await api.dispose();

  await page.goto("/journeys");
  const name = `e2e publish ${Date.now()}`;
  await page.getByLabel("Name", { exact: true }).fill(name);
  await page.getByRole("button", { name: "Create" }).click();
  await page.getByRole("link", { name: "Edit", exact: true }).click();
  for (const type of ["send_template", "wait", "wait_for_reply", "branch"]) {
    await page.getByRole("button", { name: `Add ${type}`, exact: true }).click();
  }
  await expect(page.getByRole("button", { name: "Publish" })).toBeDisabled();
  await expect(page.getByRole("list", { name: "Problems" })).toContainText("choose a template");

  // Selects by name: a wrapping label's text includes the option list, and React Flow edges
  // carry aria-labels with node ids, so getByLabel("Template") would match several elements.
  const field = (name: string) => page.locator(`select[name="${name}"]`);
  const apply = () => page.getByRole("button", { name: "Apply" }).click();
  /** Click the node, then wait for its form: the panel swaps after the selection settles. */
  const select = async (id: string) => {
    await page.locator(".react-flow__node").filter({ hasText: id }).click();
    await expect(page.getByText(`id: ${id}`, { exact: true })).toBeVisible();
  };
  await select("start");
  await field("next").selectOption("send_template_1");
  await apply();
  await select("send_template_1");
  await field("template_id").selectOption({ label: `${template} (pl)` });
  await page.getByPlaceholder("contact.first_name").fill("contact.first_name");
  await field("next").selectOption("wait_1");
  await apply();
  await select("wait_1");
  await field("next").selectOption("wait_for_reply_1");
  await apply();
  await select("wait_for_reply_1");
  await field("onReply").selectOption("branch_1");
  await field("onTimeout").selectOption("end");
  await apply();
  await select("branch_1");
  await page.getByRole("button", { name: "Add condition" }).click();
  await page.getByPlaceholder("reply.button_payload").fill("reply.button_payload");
  await page.getByPlaceholder("YES").fill("YES");
  await field("conditions.0.next").selectOption("end");
  await field("else").selectOption("end");
  await apply();

  await expect(page.getByText("Ready to publish.")).toBeVisible();
  await page.getByRole("button", { name: "Publish" }).click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  const row = page.getByRole("row").filter({ hasText: /published/ }); // not the header's "Published"
  await expect(row).toHaveCount(1);
  await expect(row).toContainText("6"); // nodes
});
