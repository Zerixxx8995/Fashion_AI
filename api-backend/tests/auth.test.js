/**
 * Auth + User Profile Tests — api-backend.
 *
 * Tests the Step 10 implementation using supertest + SQLite in-memory DB.
 * All Clerk JWT verification is bypassed by injecting req.auth directly
 * via a test-only mock middleware.
 *
 * Requirements tested (from build order Step 10):
 *   ✓ POST /auth/sync creates user in DB (201)
 *   ✓ POST /auth/sync is idempotent (second call returns 200, not 201)
 *   ✓ GET /users/:id returns profile (200)
 *   ✓ GET /users/:id returns 404 for unknown user
 *   ✓ PUT /users/:id/profile updates allowed fields
 *   ✓ PUT /users/:id/profile returns 404 for unknown user
 *   ✓ Unauthenticated requests rejected 401
 *   ✓ Bad sync body rejected 422
 *   ✓ Bad profile update body rejected 422
 */

'use strict';

process.env.TESTING = '1';
process.env.DATABASE_URL = 'sqlite::memory:';

const request = require('supertest');
const createApp = require('../src/app');
const sequelize = require('../src/db/connection');
const User = require('../src/models/User');

// ---------------------------------------------------------------------------
// App wiring: inject a mock authMiddleware that attaches req.auth from
// the X-Test-Auth header (value = clerk_id) without hitting Clerk JWKS.
// The real authMiddleware is bypassed in TESTING=1 mode.
// ---------------------------------------------------------------------------

const app = createApp();

// Test helper: build auth middleware that injects req.auth from header
function withTestAuth(clerkId) {
  return { 'X-Test-Clerk-Id': clerkId };
}

// Patch authMiddleware for tests: read from header instead of JWT
// We do this by overriding the route-level middleware via Jest module mock.
// Because authMiddleware is imported inside routes, we mock the module directly.
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

// ---------------------------------------------------------------------------
// Setup: sync DB schema before all tests, clean User table between tests
// ---------------------------------------------------------------------------

beforeAll(async () => {
  await sequelize.sync({ force: true });
});

afterEach(async () => {
  await User.destroy({ where: {}, truncate: true });
});

afterAll(async () => {
  await sequelize.close();
});

// ---------------------------------------------------------------------------
// POST /auth/sync
// ---------------------------------------------------------------------------

describe('POST /auth/sync', () => {
  const CLERK_ID = 'user_test_abc123';
  const BODY = { email: 'test@example.com', name: 'Test User' };

  test('creates a new user and returns 201', async () => {
    const res = await request(app)
      .post('/auth/sync')
      .set(withTestAuth(CLERK_ID))
      .send(BODY);

    expect(res.status).toBe(201);
    expect(res.body).toHaveProperty('user');
    expect(res.body.user.clerk_id).toBe(CLERK_ID);
    expect(res.body.user.email).toBe(BODY.email);
  });

  test('returns 200 (not 201) on second sync call (idempotent)', async () => {
    await request(app).post('/auth/sync').set(withTestAuth(CLERK_ID)).send(BODY);
    const res = await request(app).post('/auth/sync').set(withTestAuth(CLERK_ID)).send(BODY);

    expect(res.status).toBe(200);
    expect(res.body.user.clerk_id).toBe(CLERK_ID);
  });

  test('synced user has all expected fields', async () => {
    const res = await request(app)
      .post('/auth/sync')
      .set(withTestAuth(CLERK_ID))
      .send(BODY);

    const { user } = res.body;
    expect(user).toHaveProperty('id');
    expect(user).toHaveProperty('clerk_id');
    expect(user).toHaveProperty('email');
    expect(user).toHaveProperty('created_at');
  });

  test('returns 401 with no auth header', async () => {
    const res = await request(app)
      .post('/auth/sync')
      .send(BODY);

    expect(res.status).toBe(401);
    expect(res.body).toHaveProperty('error', 'Unauthorized');
    expect(res.body).toHaveProperty('status_code', 401);
  });

  test('returns 422 for missing email', async () => {
    const res = await request(app)
      .post('/auth/sync')
      .set(withTestAuth(CLERK_ID))
      .send({ clerk_id: CLERK_ID });  // no email

    expect(res.status).toBe(422);
    expect(res.body).toHaveProperty('error', 'Validation Error');
  });

  test('returns 422 for invalid email format', async () => {
    const res = await request(app)
      .post('/auth/sync')
      .set(withTestAuth(CLERK_ID))
      .send({ email: 'not-an-email', clerk_id: CLERK_ID });

    expect(res.status).toBe(422);
  });

  test('sync without name field succeeds (name is optional)', async () => {
    const res = await request(app)
      .post('/auth/sync')
      .set(withTestAuth(CLERK_ID))
      .send({ email: 'test@example.com' });

    expect(res.status).toBe(201);
    expect(res.body.user.name).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// GET /users/:id/profile
// ---------------------------------------------------------------------------

describe('GET /users/:id/profile', () => {
  const CLERK_ID = 'user_get_test';

  async function createUser() {
    return User.create({
      clerk_id: CLERK_ID,
      email: 'get@example.com',
      name: 'Get User',
    });
  }

  test('returns 200 and user profile for existing user', async () => {
    const user = await createUser();

    const res = await request(app)
      .get(`/users/${user.id}/profile`)
      .set(withTestAuth(CLERK_ID));

    expect(res.status).toBe(200);
    expect(res.body).toHaveProperty('user');
    expect(res.body.user.id).toBe(user.id);
    expect(res.body.user.email).toBe('get@example.com');
  });

  test('returns 404 for non-existent user UUID', async () => {
    const fakeId = '00000000-0000-0000-0000-000000000000';

    const res = await request(app)
      .get(`/users/${fakeId}/profile`)
      .set(withTestAuth(CLERK_ID));

    expect(res.status).toBe(404);
    expect(res.body).toHaveProperty('error', 'Not Found');
    expect(res.body).toHaveProperty('status_code', 404);
  });

  test('returns 401 without auth header', async () => {
    const user = await createUser();

    const res = await request(app)
      .get(`/users/${user.id}/profile`);

    expect(res.status).toBe(401);
  });

  test('returned profile contains expected keys', async () => {
    const user = await createUser();

    const res = await request(app)
      .get(`/users/${user.id}/profile`)
      .set(withTestAuth(CLERK_ID));

    const { user: profile } = res.body;
    ['id', 'clerk_id', 'email', 'created_at'].forEach(key => {
      expect(profile).toHaveProperty(key);
    });
  });
});

// ---------------------------------------------------------------------------
// PUT /users/:id/profile
// ---------------------------------------------------------------------------

describe('PUT /users/:id/profile', () => {
  const CLERK_ID = 'user_put_test';

  async function createUser() {
    return User.create({
      clerk_id: CLERK_ID,
      email: 'put@example.com',
      name: 'Put User',
    });
  }

  test('updates body_type and returns updated user', async () => {
    const user = await createUser();

    const res = await request(app)
      .put(`/users/${user.id}/profile`)
      .set(withTestAuth(CLERK_ID))
      .send({ body_type: 'athletic' });

    expect(res.status).toBe(200);
    expect(res.body.user.body_type).toBe('athletic');
  });

  test('updates height_cm and weight_kg', async () => {
    const user = await createUser();

    const res = await request(app)
      .put(`/users/${user.id}/profile`)
      .set(withTestAuth(CLERK_ID))
      .send({ height_cm: 170, weight_kg: 65 });

    expect(res.status).toBe(200);
    expect(res.body.user.height_cm).toBe(170);
    expect(res.body.user.weight_kg).toBe(65);
  });

  test('updates style_preferences array', async () => {
    const user = await createUser();

    const res = await request(app)
      .put(`/users/${user.id}/profile`)
      .set(withTestAuth(CLERK_ID))
      .send({ style_preferences: ['casual', 'streetwear'] });

    expect(res.status).toBe(200);
    expect(res.body.user.style_preferences).toEqual(['casual', 'streetwear']);
  });

  test('returns 404 for non-existent user', async () => {
    const fakeId = '00000000-0000-0000-0000-000000000000';

    const res = await request(app)
      .put(`/users/${fakeId}/profile`)
      .set(withTestAuth(CLERK_ID))
      .send({ body_type: 'slim' });

    expect(res.status).toBe(404);
    expect(res.body).toHaveProperty('error', 'Not Found');
  });

  test('returns 401 without auth header', async () => {
    const user = await createUser();

    const res = await request(app)
      .put(`/users/${user.id}/profile`)
      .send({ body_type: 'athletic' });

    expect(res.status).toBe(401);
  });

  test('returns 422 for invalid height_cm', async () => {
    const user = await createUser();

    const res = await request(app)
      .put(`/users/${user.id}/profile`)
      .set(withTestAuth(CLERK_ID))
      .send({ height_cm: -5 });

    expect(res.status).toBe(422);
    expect(res.body).toHaveProperty('error', 'Validation Error');
  });

  test('returns 422 for invalid style_preferences (not array)', async () => {
    const user = await createUser();

    const res = await request(app)
      .put(`/users/${user.id}/profile`)
      .set(withTestAuth(CLERK_ID))
      .send({ style_preferences: 'casual' });  // string, not array

    expect(res.status).toBe(422);
  });

  test('ignores unknown fields (whitelist)', async () => {
    const user = await createUser();

    const res = await request(app)
      .put(`/users/${user.id}/profile`)
      .set(withTestAuth(CLERK_ID))
      .send({ hacker_field: 'injected', body_type: 'slim' });

    expect(res.status).toBe(200);
    expect(res.body.user).not.toHaveProperty('hacker_field');
    expect(res.body.user.body_type).toBe('slim');
  });
});

// ---------------------------------------------------------------------------
// Health check (no auth required)
// ---------------------------------------------------------------------------

describe('GET /health', () => {
  test('returns 200 with no auth header', async () => {
    const res = await request(app).get('/health');
    expect(res.status).toBe(200);
    expect(res.body.status).toBe('ok');
  });
});
