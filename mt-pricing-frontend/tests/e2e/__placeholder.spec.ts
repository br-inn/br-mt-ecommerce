import { test, expect } from "@playwright/test";

test("home redirects or renders placeholder shell", async ({ page }) => {
  const response = await page.goto("/");
  expect(response?.status()).toBeLessThan(500);
  await expect(page).toHaveURL(/\/(login|dashboard|)$/);
});
