import { expect, test } from '@playwright/test';

test('demo login creates and reloads a reminder through the dashboard API', async ({ page }) => {
  const deadlines: Array<Record<string, unknown>> = [];
  let createdDeadlineRequests = 0;
  await page.route('http://127.0.0.1:8001/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path.endsWith('/auth/register') && request.method() === 'POST') {
      await route.fulfill({ status: 201, json: { student_id: 'student-demo', access_token: 'e2e-demo-token', token_type: 'bearer' } });
    } else if (path.endsWith('/deadlines') && request.method() === 'POST') {
      const body = request.postDataJSON();
      createdDeadlineRequests += 1;
      deadlines.push({ id: 'deadline-demo', ...body, completed_at: null });
      await route.fulfill({ status: 201, json: deadlines.at(-1) });
    } else if (path.endsWith('/deadlines') && request.method() === 'GET') {
      await route.fulfill({ status: 200, json: deadlines });
    } else if (path.endsWith('/reminders') || path.endsWith('/voice/sessions') || path.endsWith('/calls')) {
      await route.fulfill({ status: 200, json: [] });
    } else {
      await route.fulfill({ status: 200, json: {} });
    }
  });

  await page.goto('/');
  await page.getByRole('button', { name: /new here/i }).click();
  await page.getByLabel('Email').fill('student@example.com');
  await page.getByLabel('Password').fill('A-long-demo-password-2026');
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible();

  await page.getByPlaceholder('e.g. Algebra assignment').fill('Biology assignment');
  await page.locator('input[type="datetime-local"]').fill('2027-01-15T15:00');
  await page.getByRole('button', { name: /add deadline/i }).click();
  await expect(page.getByText('Biology assignment')).toBeVisible();
  await expect(page.getByRole('status')).toHaveText('Deadline saved and reminder scheduled.');
  expect(createdDeadlineRequests).toBe(1);
  expect(await page.evaluate(() => localStorage.getItem('accessToken'))).toBe('e2e-demo-token');
});
