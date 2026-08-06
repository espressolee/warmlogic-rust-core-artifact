const { test, expect } = require('@playwright/test');

test('keyboard navigation smoke', async ({ page }) => {
  await page.goto('data:text/html,<button id="a">A</button><button id="b">B</button>');
  await page.keyboard.press('Tab');
  await expect(page.locator('#a')).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.locator('#b')).toBeFocused();
});
