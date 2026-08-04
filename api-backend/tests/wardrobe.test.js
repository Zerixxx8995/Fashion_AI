/**
 * Wardrobe CRUD Tests — api-backend.
 *
 * Tests:
 *   POST /wardrobe          — adds item, validates fields, enforces auth
 *   GET  /wardrobe/:userId  — returns user's items, 401 without auth
 *   DELETE /wardrobe/:id   — removes item, 404 on unknown, 401 without auth
 *
 * Strategy:
 *   - TESTING=1, SQLite in-memory, jest.mock for authMiddleware
 */

'use strict';

process.env.TESTING = '1';
process.env.DATABASE_URL = 'sqlite::memory:';

const request = require('supertest');

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

const createApp = require('../src/app');
const sequelize = require('../src/db/connection');
const WardrobeItem = require('../src/models/WardrobeItem');
const User = require('../src/models/User');
const Product = require('../src/models/Product');

let app;

const TEST_CLERK_ID = 'user_wardrobe_test_clerk';
const TEST_USER_UUID = 'aaaa0000-0000-0000-0000-000000000001';
const TEST_PRODUCT_UUID = 'bbbb0000-0000-0000-0000-000000000002';

function auth() {
  return { 'x-test-clerk-id': TEST_CLERK_ID };
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeAll(async () => {
  await sequelize.sync({ force: true });
  app = createApp();

  await User.create({
    id: TEST_USER_UUID,
    clerk_id: TEST_CLERK_ID,
    email: 'wardrobe-test@example.com',
    name: 'Wardrobe Tester',
  });

  await Product.create({
    id: TEST_PRODUCT_UUID,
    platform: 'myntra',
    platform_id: 'myntra-wardrobe-001',
    name: 'Test Kurta',
    price_inr: 1200,
    url: 'https://myntra.com/test-kurta',
  });
});

afterAll(async () => {
  await sequelize.close();
});

beforeEach(async () => {
  await WardrobeItem.destroy({ where: {} });
});

// ---------------------------------------------------------------------------
// POST /wardrobe
// ---------------------------------------------------------------------------

describe('POST /wardrobe', () => {
  test('creates item and returns 201', async () => {
    const res = await request(app)
      .post('/wardrobe')
      .set(auth())
      .send({
        user_id: TEST_USER_UUID,
        name: 'Blue Kurta',
        category: 'ethnic',
        color: 'blue',
        purchase_price_inr: 1200,
      });

    expect(res.status).toBe(201);
    expect(res.body).toHaveProperty('item');
    expect(res.body.item.name).toBe('Blue Kurta');
    expect(res.body.item.user_id).toBe(TEST_USER_UUID);
    expect(res.body.item.category).toBe('ethnic');
    expect(res.body.item.times_worn).toBe(0);
  });

  test('creates item without optional fields', async () => {
    const res = await request(app)
      .post('/wardrobe')
      .set(auth())
      .send({ user_id: TEST_USER_UUID, name: 'Mystery Item' });

    expect(res.status).toBe(201);
    expect(res.body.item.category).toBeNull();
    expect(res.body.item.color).toBeNull();
  });

  test('creates item with product_id link', async () => {
    const res = await request(app)
      .post('/wardrobe')
      .set(auth())
      .send({
        user_id: TEST_USER_UUID,
        name: 'Linked Kurta',
        product_id: TEST_PRODUCT_UUID,
        category: 'ethnic',
      });

    expect(res.status).toBe(201);
    expect(res.body.item.product_id).toBe(TEST_PRODUCT_UUID);
  });

  test('returns 401 without auth', async () => {
    const res = await request(app)
      .post('/wardrobe')
      .send({ user_id: TEST_USER_UUID, name: 'Test' });
    expect(res.status).toBe(401);
  });

  test('returns 422 for missing name', async () => {
    const res = await request(app)
      .post('/wardrobe')
      .set(auth())
      .send({ user_id: TEST_USER_UUID });
    expect(res.status).toBe(422);
    expect(res.body.detail).toMatch(/name/);
  });

  test('returns 422 for invalid user_id', async () => {
    const res = await request(app)
      .post('/wardrobe')
      .set(auth())
      .send({ user_id: 'not-a-uuid', name: 'Test' });
    expect(res.status).toBe(422);
  });

  test('returns 422 for invalid product_id', async () => {
    const res = await request(app)
      .post('/wardrobe')
      .set(auth())
      .send({ user_id: TEST_USER_UUID, name: 'Test', product_id: 'bad-uuid' });
    expect(res.status).toBe(422);
  });

  test('returns 422 for negative purchase_price_inr', async () => {
    const res = await request(app)
      .post('/wardrobe')
      .set(auth())
      .send({ user_id: TEST_USER_UUID, name: 'Test', purchase_price_inr: -100 });
    expect(res.status).toBe(422);
  });

  test('item has id field after creation', async () => {
    const res = await request(app)
      .post('/wardrobe')
      .set(auth())
      .send({ user_id: TEST_USER_UUID, name: 'Has ID' });
    expect(res.status).toBe(201);
    expect(res.body.item).toHaveProperty('id');
  });
});

// ---------------------------------------------------------------------------
// GET /wardrobe/:userId
// ---------------------------------------------------------------------------

describe('GET /wardrobe/:userId', () => {
  test('returns empty array when user has no items', async () => {
    const res = await request(app)
      .get(`/wardrobe/${TEST_USER_UUID}`)
      .set(auth());

    expect(res.status).toBe(200);
    expect(res.body.items).toEqual([]);
    expect(res.body.count).toBe(0);
  });

  test('returns all items for user', async () => {
    await WardrobeItem.create({ user_id: TEST_USER_UUID, name: 'Jeans', category: 'bottoms' });
    await WardrobeItem.create({ user_id: TEST_USER_UUID, name: 'Kurta', category: 'ethnic' });

    const res = await request(app)
      .get(`/wardrobe/${TEST_USER_UUID}`)
      .set(auth());

    expect(res.status).toBe(200);
    expect(res.body.count).toBe(2);
    expect(res.body.items).toHaveLength(2);
  });

  test('returns 401 without auth', async () => {
    const res = await request(app).get(`/wardrobe/${TEST_USER_UUID}`);
    expect(res.status).toBe(401);
  });

  test('returns 422 for invalid userId', async () => {
    const res = await request(app)
      .get('/wardrobe/not-a-valid-uuid')
      .set(auth());
    expect(res.status).toBe(422);
  });

  test('each item has required fields', async () => {
    await WardrobeItem.create({ user_id: TEST_USER_UUID, name: 'T-Shirt', category: 'tops' });

    const res = await request(app)
      .get(`/wardrobe/${TEST_USER_UUID}`)
      .set(auth());

    const item = res.body.items[0];
    expect(item).toHaveProperty('id');
    expect(item).toHaveProperty('user_id');
    expect(item).toHaveProperty('name');
    expect(item).toHaveProperty('times_worn');
  });
});

// ---------------------------------------------------------------------------
// DELETE /wardrobe/:id
// ---------------------------------------------------------------------------

describe('DELETE /wardrobe/:id', () => {
  test('deletes item and returns 200', async () => {
    const created = await WardrobeItem.create({
      user_id: TEST_USER_UUID,
      name: 'To Delete',
    });

    const res = await request(app)
      .delete(`/wardrobe/${created.id}`)
      .set(auth());

    expect(res.status).toBe(200);
    expect(res.body.id).toBe(created.id);

    const found = await WardrobeItem.findByPk(created.id);
    expect(found).toBeNull();
  });

  test('returns 404 for non-existent item', async () => {
    const res = await request(app)
      .delete('/wardrobe/00000000-0000-0000-0000-000000000099')
      .set(auth());
    expect(res.status).toBe(404);
  });

  test('returns 401 without auth', async () => {
    const res = await request(app)
      .delete('/wardrobe/00000000-0000-0000-0000-000000000099');
    expect(res.status).toBe(401);
  });

  test('returns 422 for invalid id format', async () => {
    const res = await request(app)
      .delete('/wardrobe/not-a-uuid')
      .set(auth());
    expect(res.status).toBe(422);
  });
});
