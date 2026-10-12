const { test, expect } = require("@playwright/test");

const baseURL = process.env.SYNTAX_LOCAL_AI_URL || "http://127.0.0.1:8000";
const viewports = [
  { name: "mobile-320", width: 320, height: 800 },
  { name: "mobile-375", width: 375, height: 812 },
  { name: "tablet-768", width: 768, height: 900 },
  { name: "desktop-1024", width: 1024, height: 900 },
];
const publicPages = ["/", "/login/", "/signup/"];

for (const viewport of viewports) {
  test.describe(`${viewport.name} (${viewport.width}px)`, () => {
    test(`public pages fit without horizontal overflow`, async ({ browser }) => {
      const context = await browser.newContext({ viewport });
      const page = await context.newPage();

      for (const path of publicPages) {
        await page.goto(`${baseURL}${path}`, { waitUntil: "domcontentloaded" });
        await expect(page.locator("body")).toBeVisible();
        await expect(page.locator('meta[name="viewport"]')).toHaveAttribute("content", /width=device-width/);
        const layout = await page.evaluate(() => ({
          clientWidth: document.documentElement.clientWidth,
          scrollWidth: document.documentElement.scrollWidth,
        }));
        expect(layout.scrollWidth, `${path} overflows at ${viewport.width}px`).toBeLessThanOrEqual(layout.clientWidth + 1);
      }

      await context.close();
    });
  });
}

test("authenticated workspace smoke test can use a supplied storage state", async ({ browser }) => {
  test.skip(!process.env.SYNTAX_LOCAL_AI_STORAGE, "Set SYNTAX_LOCAL_AI_STORAGE to run the authenticated workspace smoke test.");
  const context = await browser.newContext({
    storageState: process.env.SYNTAX_LOCAL_AI_STORAGE,
    viewport: { width: 375, height: 812 },
  });
  const page = await context.newPage();
  await page.goto(`${baseURL}/`, { waitUntil: "domcontentloaded" });
  await expect(page.locator(".chat-box")).toBeVisible();
  await expect(page.locator(".composer")).toBeVisible();
  await expect(page.locator("#codingCenterPanel")).toBeAttached();
  await page.screenshot({ path: "test-results/workspace-mobile-375.png", fullPage: true });
  await context.close();
});
