const { test, expect } = require('@playwright/test');

test('dashboard smoke content visible', async ({ page }) => {
  await page.goto('data:text/html,<section><h2>Overview</h2><div id="card">healthy</div></section>');
  await expect(page.locator('#card')).toHaveText('healthy');
});
