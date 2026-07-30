/**
 * Alert System Tests — api-backend.
 *
 * Tests:
 *   POST /alerts            — creates alert, validates fields, enforces auth
 *   GET  /alerts/:userId    — returns user alerts
 *   DELETE /alerts/:id      — removes alert, 404 on unknown
 *   Internal /check-prices  — fires Socket.io event and deactivates alert when threshold crossed
 *   Internal /check-restock — fires restock event for watched products
 *
 * Strategy:
 *   - TESTING=1 to bypass Clerk auth
 *   - X-Test-Clerk-Id header injects auth identity (same pattern as auth.test.js)
 *   - SQLite in-memory database
 *   - Socket.io not initialised; emitToUser is mocked to a jest.fn()
 */

'use strict';

process.env.TESTING = '1';
process.env.DATABASE_URL = 'sqlite::memory:';
process.env.INTERNAL_API_SECRET = 'test-internal-secret';

const request = require('supertest');

// Mock authMiddleware to bypass Clerk JWT — inject identity via X-Test-Clerk-Id header
jest.mock('../src/middleware/authMiddleware', () => {
  return async function mockAuthMiddleware(req, res, next) {
    const clerkId = req.headers['x-test-clerk-id'];
    if (!clerkId) {
      return res.status(401).json({
        error: 'Unauthorized',
        detail: "Missing or malformed Authorization header. Expected: 'Bearer <token>'",
        status_code: 401,
      });
    }
    req.auth = { sub: clerkId };
    return next();
  };
});

// Mock Socket.io manager so we can spy on emitToUser without needing a live WS server
jest.mock('../src/integrations/socketManager', () => ({
  initSocket: jest.fn(),
  getIO: jest.fn(),
  emitToUser: jest.fn(),
}));

const { emitToUser } = require('../src/integrations/socketManager');
const createApp = require('../src/app');
const sequelize = require('../src/db/connection');

// Models — must be imported after connection so Sequelize registers them
const Alert = require('../src/models/Alert');
const User = require('../src/models/User');
const Product = require('../src/models/Product');

let app;

// UUIDs for test data
const TEST_CLERK_ID = 'user_alerts_test_clerk_id';
const TEST_USER_UUID = '11111111-1111-1111-1111-111111111111';
const TEST_PRODUCT_UUID = '22222222-2222-2222-2222-222222222222';
const OTHER_USER_UUID = '33333333-3333-3333-3333-333333333333';

function withTestAuth(clerkId) {
  return { 'x-test-clerk-id': clerkId };
}

// ---------------------------------------------------------------------------
// Setup + Teardown
// ---------------------------------------------------------------------------

beforeAll(async () => {
  await sequelize.sync({ force: true });
  app = createApp();

  // Create a test user that the auth middleware will find
  await User.create({
    id: TEST_USER_UUID,
    clerk_id: TEST_CLERK_ID,
    email: 'alerts-test@example.com',
    name: 'Alert Tester',
  });

  // Create a test product for FK references
  await Product.create({
    id: TEST_PRODUCT_UUID,
    platform: 'myntra',
    platform_id: 'myntra-alerts-test-001',
    name: 'Test Kurta',
    price_inr: 2000,
    url: 'https://myntra.com/test-kurta',
  });
});

afterAll(async () => {
  await sequelize.close();
});

beforeEach(async () => {
  await Alert.destroy({ where: {} });
  emitToUser.mockClear();
});

// ---------------------------------------------------------------------------
// POST /alerts
// ---------------------------------------------------------------------------

describe('POST /alerts', () => {
  test('creates a price_drop alert and returns 201', async () => {
    const res = await request(app)
      .post('/alerts')
      .set(withTestAuth(TEST_CLERK_ID))
      .send({
        user_id: TEST_USER_UUID,
        product_id: TEST_PRODUCT_UUID,
        alert_type: 'price_drop',
        target_price_inr: 1500,
      });

    expect(res.status).toBe(201);
    expect(res.body).toHaveProperty('alert');
    expect(res.body.alert.user_id).toBe(TEST_USER_UUID);
    expect(res.body.alert.alert_type).toBe('price_drop');
    expect(res.body.alert.target_price_inr).toBe(1500);
    expect(res.body.alert.is_active).toBe(true);
  });

  test('creates a restock alert and returns 201', async () => {
    const res = await request(app)
      .post('/alerts')
      .set(withTestAuth(TEST_CLERK_ID))
      .send({
        user_id: TEST_USER_UUID,
        product_id: TEST_PRODUCT_UUID,
        alert_type: 'restock',
      });

    expect(res.status).toBe(201);
    expect(res.body.alert.alert_type).toBe('restock');
    expect(res.body.alert.target_price_inr).toBeNull();
  });

  test('returns 401 without auth header', async () => {
    const res = await request(app)
      .post('/alerts')
      .send({
        user_id: TEST_USER_UUID,
        product_id: TEST_PRODUCT_UUID,
        alert_type: 'price_drop',
        target_price_inr: 1500,
      });
    expect(res.status).toBe(401);
  });

  test('returns 422 for invalid alert_type', async () => {
    const res = await request(app)
      .post('/alerts')
      .set(withTestAuth(TEST_CLERK_ID))
      .send({
        user_id: TEST_USER_UUID,
        product_id: TEST_PRODUCT_UUID,
        alert_type: 'invalid_type',
      });
    expect(res.status).toBe(422);
    expect(res.body.detail).toMatch(/alert_type/);
  });

  test('returns 422 for price_drop without target_price_inr', async () => {
    const res = await request(app)
      .post('/alerts')
      .set(withTestAuth(TEST_CLERK_ID))
      .send({
        user_id: TEST_USER_UUID,
        product_id: TEST_PRODUCT_UUID,
        alert_type: 'price_drop',
        // target_price_inr intentionally missing
      });
    expect(res.status).toBe(422);
    expect(res.body.detail).toMatch(/target_price_inr/);
  });

  test('returns 422 for invalid user_id UUID', async () => {
    const res = await request(app)
      .post('/alerts')
      .set(withTestAuth(TEST_CLERK_ID))
      .send({
        user_id: 'not-a-uuid',
        product_id: TEST_PRODUCT_UUID,
        alert_type: 'restock',
      });
    expect(res.status).toBe(422);
    expect(res.body.detail).toMatch(/user_id/);
  });

  test('new alert has is_active = true by default', async () => {
    const res = await request(app)
      .post('/alerts')
      .set(withTestAuth(TEST_CLERK_ID))
      .send({
        user_id: TEST_USER_UUID,
        product_id: TEST_PRODUCT_UUID,
        alert_type: 'restock',
      });
    expect(res.status).toBe(201);
    expect(res.body.alert.is_active).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// GET /alerts/:userId
// ---------------------------------------------------------------------------

describe('GET /alerts/:userId', () => {
  test('returns 200 and empty array when user has no alerts', async () => {
    const res = await request(app)
      .get(`/alerts/${TEST_USER_UUID}`)
      .set(withTestAuth(TEST_CLERK_ID));

    expect(res.status).toBe(200);
    expect(res.body.alerts).toEqual([]);
    expect(res.body.count).toBe(0);
  });

  test('returns all alerts for a user', async () => {
    // Create two alerts
    await Alert.create({
      user_id: TEST_USER_UUID,
      product_id: TEST_PRODUCT_UUID,
      alert_type: 'price_drop',
      target_price_inr: 1200,
    });
    await Alert.create({
      user_id: TEST_USER_UUID,
      product_id: TEST_PRODUCT_UUID,
      alert_type: 'restock',
    });

    const res = await request(app)
      .get(`/alerts/${TEST_USER_UUID}`)
      .set(withTestAuth(TEST_CLERK_ID));

    expect(res.status).toBe(200);
    expect(res.body.count).toBe(2);
    expect(res.body.alerts).toHaveLength(2);
  });

  test('returns 401 without auth header', async () => {
    const res = await request(app).get(`/alerts/${TEST_USER_UUID}`);
    expect(res.status).toBe(401);
  });

  test('returns 422 for invalid userId UUID', async () => {
    const res = await request(app)
      .get('/alerts/not-a-valid-uuid')
      .set(withTestAuth(TEST_CLERK_ID));
    expect(res.status).toBe(422);
  });

  test('alert response contains expected keys', async () => {
    await Alert.create({
      user_id: TEST_USER_UUID,
      product_id: TEST_PRODUCT_UUID,
      alert_type: 'restock',
    });

    const res = await request(app)
      .get(`/alerts/${TEST_USER_UUID}`)
      .set(withTestAuth(TEST_CLERK_ID));

    const alert = res.body.alerts[0];
    expect(alert).toHaveProperty('id');
    expect(alert).toHaveProperty('user_id');
    expect(alert).toHaveProperty('product_id');
    expect(alert).toHaveProperty('alert_type');
    expect(alert).toHaveProperty('is_active');
    expect(alert).toHaveProperty('created_at');
  });
});

// ---------------------------------------------------------------------------
// DELETE /alerts/:id
// ---------------------------------------------------------------------------

describe('DELETE /alerts/:id', () => {
  test('deletes an alert and returns 200', async () => {
    const created = await Alert.create({
      user_id: TEST_USER_UUID,
      product_id: TEST_PRODUCT_UUID,
      alert_type: 'restock',
    });

    const res = await request(app)
      .delete(`/alerts/${created.id}`)
      .set(withTestAuth(TEST_CLERK_ID));

    expect(res.status).toBe(200);
    expect(res.body.id).toBe(created.id);

    // Verify it's gone from DB
    const found = await Alert.findByPk(created.id);
    expect(found).toBeNull();
  });

  test('returns 404 for non-existent alert', async () => {
    const res = await request(app)
      .delete('/alerts/00000000-0000-0000-0000-000000000099')
      .set(withTestAuth(TEST_CLERK_ID));
    expect(res.status).toBe(404);
  });

  test('returns 401 without auth header', async () => {
    const res = await request(app)
      .delete('/alerts/00000000-0000-0000-0000-000000000099');
    expect(res.status).toBe(401);
  });
});

// ---------------------------------------------------------------------------
// Internal: POST /internal/check-prices  (Celery → Node)
// ---------------------------------------------------------------------------

describe('Internal: POST /internal/check-prices', () => {
  test('fires emitToUser and deactivates alert when price threshold crossed', async () => {
    const alert = await Alert.create({
      user_id: TEST_USER_UUID,
      product_id: TEST_PRODUCT_UUID,
      alert_type: 'price_drop',
      target_price_inr: 1500,
      is_active: true,
    });

    const res = await request(app)
      .post('/internal/check-prices')
      .set('x-internal-secret', 'test-internal-secret')
      .send({ prices: { [TEST_PRODUCT_UUID]: 1200 } }); // 1200 < 1500 threshold

    expect(res.status).toBe(200);
    expect(res.body.fired).toBe(1);
    expect(emitToUser).toHaveBeenCalledWith(
      TEST_USER_UUID,
      'price_drop',
      expect.objectContaining({
        alertId: alert.id,
        productId: TEST_PRODUCT_UUID,
        targetPrice: 1500,
        currentPrice: 1200,
      })
    );

    // Alert should be deactivated
    const refreshed = await Alert.findByPk(alert.id);
    expect(refreshed.is_active).toBe(false);
  });

  test('does NOT fire emitToUser when price is above threshold', async () => {
    await Alert.create({
      user_id: TEST_USER_UUID,
      product_id: TEST_PRODUCT_UUID,
      alert_type: 'price_drop',
      target_price_inr: 1500,
      is_active: true,
    });

    const res = await request(app)
      .post('/internal/check-prices')
      .set('x-internal-secret', 'test-internal-secret')
      .send({ prices: { [TEST_PRODUCT_UUID]: 1800 } }); // 1800 > 1500, no fire

    expect(res.status).toBe(200);
    expect(res.body.fired).toBe(0);
    expect(emitToUser).not.toHaveBeenCalled();
  });

  test('returns 401 without internal secret', async () => {
    const res = await request(app)
      .post('/internal/check-prices')
      .send({ prices: {} });
    expect(res.status).toBe(401);
  });
});

// ---------------------------------------------------------------------------
// Internal: POST /internal/check-restock
// ---------------------------------------------------------------------------

describe('Internal: POST /internal/check-restock', () => {
  test('fires restock emitToUser for matching product', async () => {
    const alert = await Alert.create({
      user_id: TEST_USER_UUID,
      product_id: TEST_PRODUCT_UUID,
      alert_type: 'restock',
      is_active: true,
    });

    const res = await request(app)
      .post('/internal/check-restock')
      .set('x-internal-secret', 'test-internal-secret')
      .send({ restocked_product_ids: [TEST_PRODUCT_UUID] });

    expect(res.status).toBe(200);
    expect(res.body.fired).toBe(1);
    expect(emitToUser).toHaveBeenCalledWith(
      TEST_USER_UUID,
      'restock',
      expect.objectContaining({
        alertId: alert.id,
        productId: TEST_PRODUCT_UUID,
      })
    );

    const refreshed = await Alert.findByPk(alert.id);
    expect(refreshed.is_active).toBe(false);
  });

  test('does not fire for products not in restocked list', async () => {
    await Alert.create({
      user_id: TEST_USER_UUID,
      product_id: TEST_PRODUCT_UUID,
      alert_type: 'restock',
      is_active: true,
    });

    const res = await request(app)
      .post('/internal/check-restock')
      .set('x-internal-secret', 'test-internal-secret')
      .send({ restocked_product_ids: ['aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'] });

    expect(res.status).toBe(200);
    expect(res.body.fired).toBe(0);
    expect(emitToUser).not.toHaveBeenCalled();
  });
});
