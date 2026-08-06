const { test, expect } = require('@playwright/test');

test('a11y smoke page renders with heading', async ({ page }) => {
  await page.goto('data:text/html,<main><h1>WarmLogic Dashboard</h1><p>CI smoke.</p></main>');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('WarmLogic Dashboard');
});
