import { createHmac } from "node:crypto";
import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const EMAIL = "ala@example.org";
export const PASSWORD = "lokalne-haslo-123";
const WEBHOOK_SECRET = "e2e-webhook-secret"; // META_APP_SECRET in backend/.env

/** Creates the test user through Supabase Auth; 422 means it already exists. */
export async function ensureTestUser(api: APIRequestContext): Promise<void> {
  const response = await api.post(`${process.env.NEXT_PUBLIC_SUPABASE_URL}/auth/v1/signup`, {
    headers: { apikey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "" },
    data: { email: EMAIL, password: PASSWORD },
  });
  expect([200, 422]).toContain(response.status());
}

/** Marks a template APPROVED the way Meta would: a signed template status webhook. */
export async function approveTemplate(api: APIRequestContext, name: string): Promise<void> {
  const body = JSON.stringify({
    object: "whatsapp_business_account",
    entry: [
      {
        id: "WABA1",
        changes: [
          {
            field: "message_template_status_update",
            value: {
              event: "APPROVED",
              message_template_id: 123,
              message_template_name: name,
              message_template_language: "pl",
              reason: "NONE",
            },
          },
        ],
      },
    ],
  });
  const signature = createHmac("sha256", WEBHOOK_SECRET).update(body).digest("hex");
  const hook = await api.post(`${process.env.API_URL}/webhooks/meta`, {
    headers: { "Content-Type": "application/json", "X-Hub-Signature-256": `sha256=${signature}` },
    data: body,
  });
  expect(hook.status()).toBe(200);
}

/** Creates a Meta template draft through the creator (type tile, name, body); returns its name. */
export async function createDraft(page: Page, name = `e2e_${Date.now()}`): Promise<string> {
  await page.goto("/templates/new");
  await page.getByRole("button", { name: "Template", exact: true }).click();
  await page.getByLabel("Name", { exact: true }).fill(name);
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await page.getByLabel("Body", { exact: true }).fill("Cześć {{1}}!");
  await page.getByLabel("Example for {{1}}").fill("Ala");
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByRole("row").filter({ hasText: name })).toContainText("DRAFT");
  return name;
}

/** Creates a template draft in the panel and approves it; returns its name. */
export async function approvedTemplate(page: Page, api: APIRequestContext): Promise<string> {
  const name = await createDraft(page);
  await approveTemplate(api, name);
  return name;
}

export async function signIn(page: Page): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("E-mail").fill(EMAIL);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText(`Signed in as ${EMAIL}`)).toBeVisible();
}
