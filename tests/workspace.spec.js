const { test, expect } = require("@playwright/test");

const baseURL = process.env.SYNTAX_LOCAL_AI_URL || "http://127.0.0.1:8000";

test("login page validates required fields", async ({ page }) => {
  await page.goto(`${baseURL}/login/`, { waitUntil: "domcontentloaded" });
  await expect(page.locator('form[aria-label="Sign in form"]')).toBeVisible();
  await expect(page.locator('input[name="username"]')).toHaveAttribute("required", "");
  await expect(page.locator('input[name="password"]')).toHaveAttribute("required", "");
});

test("authenticated workspace exposes coding and runtime controls", async ({ browser }) => {
  test.skip(!process.env.SYNTAX_LOCAL_AI_STORAGE, "Set SYNTAX_LOCAL_AI_STORAGE for authenticated E2E tests.");
  const context = await browser.newContext({
    storageState: process.env.SYNTAX_LOCAL_AI_STORAGE,
    viewport: { width: 1280, height: 900 },
  });
  const page = await context.newPage();
  await page.goto(`${baseURL}/`, { waitUntil: "domcontentloaded" });
  await expect(page.locator("#codingCenterPanel")).toBeAttached();
  await expect(page.locator("#ollamaPanel")).toBeAttached();
  const diagnostics = await page.evaluate(async () => {
    const response = await fetch("/api/setup/diagnostics/");
    return { ok: response.ok, payload: await response.json() };
  });
  expect(diagnostics.ok).toBeTruthy();
  expect(diagnostics.payload).toHaveProperty("runtimes");
  await context.close();
});
