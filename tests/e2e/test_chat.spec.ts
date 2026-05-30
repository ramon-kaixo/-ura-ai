import { test, expect } from '@playwright/test';

test.describe('URA Chat E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:8000');
  });

  test('should load chat interface', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('URA');
    await expect(page.locator('#chat-input')).toBeVisible();
  });

  test('should send message and receive response', async ({ page }) => {
    const chatInput = page.locator('#chat-input');
    const sendButton = page.locator('#send-button');
    const chatResponse = page.locator('#chat-response');

    await chatInput.fill('Hola URA');
    await sendButton.click();

    await expect(chatResponse).toBeVisible({ timeout: 10000 });
    await expect(chatResponse).not.toContainText('Error');
  });

  test('should display agent list', async ({ page }) => {
    await page.click('#agents-button');
    
    const agentsList = page.locator('.agents-list');
    await expect(agentsList).toBeVisible();
    
    const agents = await agentsList.locator('.agent-item').count();
    expect(agents).toBeGreaterThan(0);
  });

  test('should handle health check', async ({ page }) => {
    const response = await page.request.get('http://localhost:8000/v2/health');
    expect(response.status()).toBe(200);
    
    const body = await response.json();
    expect(body).toHaveProperty('status');
  });

  test('should validate API documentation endpoint', async ({ page }) => {
    const response = await page.request.get('http://localhost:8000/v2/docs');
    expect(response.status()).toBe(200);
  });

  test('should handle concurrent chat sessions', async ({ page, context }) => {
    const page2 = await context.newPage();
    await page2.goto('http://localhost:8000');

    // Send message on first page
    await page.locator('#chat-input').fill('Mensaje 1');
    await page.locator('#send-button').click();

    // Send message on second page
    await page2.locator('#chat-input').fill('Mensaje 2');
    await page2.locator('#send-button').click();

    await expect(page.locator('#chat-response')).toBeVisible({ timeout: 10000 });
    await expect(page2.locator('#chat-response')).toBeVisible({ timeout: 10000 });

    await page2.close();
  });

  test('should handle slow API responses', async ({ page }) => {
    // Mock slow response
    await page.route('**/v2/chat', route => {
      setTimeout(() => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ response: 'Test response' })
      }), 3000);
    });

    await page.locator('#chat-input').fill('Test');
    await page.locator('#send-button').click();

    await expect(page.locator('#chat-response')).toBeVisible({ timeout: 5000 });
  });

  test('should display error on API failure', async ({ page }) => {
    await page.route('**/v2/chat', route => route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'Internal server error' })
    }));

    await page.locator('#chat-input').fill('Test');
    await page.locator('#send-button').click();

    await expect(page.locator('.error-message')).toBeVisible({ timeout: 5000 });
  });

  test('should persist chat history', async ({ page }) => {
    await page.locator('#chat-input').fill('Mensaje 1');
    await page.locator('#send-button').click();
    await expect(page.locator('#chat-response')).toBeVisible();

    await page.reload();
    
    const history = page.locator('.chat-history');
    await expect(history).toBeVisible();
    const messages = await history.locator('.message').count();
    expect(messages).toBeGreaterThan(0);
  });

  test('should handle long messages', async ({ page }) => {
    const longMessage = 'A'.repeat(5000);
    
    await page.locator('#chat-input').fill(longMessage);
    await page.locator('#send-button').click();

    await expect(page.locator('#chat-response')).toBeVisible({ timeout: 15000 });
  });
});
