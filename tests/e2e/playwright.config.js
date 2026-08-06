// Minimal Playwright config for CI smoke checks.
/** @type {import('@playwright/test').PlaywrightTestConfig} */
module.exports = {
  testDir: '.',
  timeout: 30_000,
  use: {
    headless: true,
  },
};
