import { expect, test } from "@playwright/test";
import { ensureTestUser, signIn } from "./helpers";

test.beforeAll(async ({ playwright }) => {
  const api = await playwright.request.newContext();
  await ensureTestUser(api);
  await api.dispose();
});

test("the creator explains Meta's variable rules while typing and saves a service message", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/templates/new");
  const next = page.getByRole("button", { name: "Next", exact: true });
  await expect(next).toBeDisabled();

  // A Meta template: named variables, a rule broken on purpose, then fixed.
  await page.getByRole("button", { name: "Template", exact: true }).click();
  await page.getByLabel("Name", { exact: true }).fill("Bad Name");
  await expect(page.getByRole("alert").filter({ hasText: "lowercase" })).toBeVisible();
  const name = `e2e_rules_${Date.now()}`;
  await page.getByLabel("Name", { exact: true }).fill(name);
  await next.click();
  await page.getByLabel("Body", { exact: true }).fill("{{first_name}} cześć");
  await expect(page.getByRole("list", { name: "Body problems" })).toContainText(
    "must not start with a variable",
  );
  await page.getByLabel("Body", { exact: true }).fill("Cześć {{first_name}}, oferta {{offer}}.");
  await expect(page.getByRole("list", { name: "Body problems" })).toHaveCount(0);
  await page.getByLabel("Example for {{first_name}}").fill("Ala");
  await page.getByLabel("Example for {{offer}}").fill("20%");
  await page.getByRole("button", { name: "Add button" }).click();
  await page.locator('input[name="buttons.0.text"]').fill("Tak");
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByRole("row").filter({ hasText: name })).toContainText("DRAFT");

  // A service message: no approval, ready at once.
  await page.goto("/templates/new");
  await page.getByRole("button", { name: "Service message", exact: true }).click();
  const serviceName = `e2e_thanks_${Date.now()}`;
  await page.getByLabel("Name", { exact: true }).fill(serviceName);
  await next.click();
  await page.getByLabel("Body", { exact: false }).fill("Dziękujemy 🙏");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  const row = page.getByRole("row").filter({ hasText: serviceName });
  await expect(row).toContainText("service message");
  await expect(row).toContainText("READY");
  await expect(row.getByRole("button", { name: "Submit" })).toHaveCount(0);
});
