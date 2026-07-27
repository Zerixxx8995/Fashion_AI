/**
 * Tests for api-backend Sequelize models.
 *
 * Plan assertions:
 *   - assert all models create tables without error
 *   - assert indexed fields are indexed
 *
 * Strategy:
 *   Uses SQLite in-memory via the DATABASE_URL env override.
 *   sequelize.sync({ force: true }) is the create-tables assertion.
 *   Index presence is verified via sequelize.getQueryInterface().showIndex().
 */

'use strict';

// Force SQLite in-memory for tests — must be set before any model import
process.env.DATABASE_URL = 'sqlite::memory:';

const { sequelize, Alert, Product, User, WardrobeItem } = require('../../src/models/index');

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

beforeAll(async () => {
  // Create all tables — this IS the "tables create without error" assertion
  await sequelize.sync({ force: true });
});

afterAll(async () => {
  await sequelize.close();
});

// ---------------------------------------------------------------------------
// TestTablesCreated — assert all models create tables without error
// ---------------------------------------------------------------------------

describe('Tables created without error', () => {
  const qi = () => sequelize.getQueryInterface();

  test('users table exists', async () => {
    const tables = await qi().showAllTables();
    expect(tables).toContain('users');
  });

  test('products table exists', async () => {
    const tables = await qi().showAllTables();
    expect(tables).toContain('products');
  });

  test('wardrobe_items table exists', async () => {
    const tables = await qi().showAllTables();
    expect(tables).toContain('wardrobe_items');
  });

  test('alerts table exists', async () => {
    const tables = await qi().showAllTables();
    expect(tables).toContain('alerts');
  });

  test('exactly 4 app tables', async () => {
    const tables = await qi().showAllTables();
    const appTables = tables.filter(t =>
      ['users', 'products', 'wardrobe_items', 'alerts'].includes(t)
    );
    expect(appTables).toHaveLength(4);
  });
});

// ---------------------------------------------------------------------------
// TestIndexes — assert indexed fields are indexed
// ---------------------------------------------------------------------------

describe('Indexed fields are indexed', () => {
  const qi = () => sequelize.getQueryInterface();

  async function getIndexedColumns(tableName) {
    const indexes = await qi().showIndex(tableName);
    const cols = new Set();
    for (const idx of indexes) {
      for (const field of idx.fields) {
        cols.add(field.attribute || field.name || field);
      }
    }
    return cols;
  }

  test('users.clerk_id is indexed', async () => {
    const cols = await getIndexedColumns('users');
    expect(cols).toContain('clerk_id');
  });

  test('products.platform is indexed', async () => {
    const cols = await getIndexedColumns('products');
    expect(cols).toContain('platform');
  });

  test('products.platform_id is indexed', async () => {
    const cols = await getIndexedColumns('products');
    expect(cols).toContain('platform_id');
  });

  test('wardrobe_items.user_id is indexed', async () => {
    const cols = await getIndexedColumns('wardrobe_items');
    expect(cols).toContain('user_id');
  });

  test('alerts.user_id is indexed', async () => {
    const cols = await getIndexedColumns('alerts');
    expect(cols).toContain('user_id');
  });
});

// ---------------------------------------------------------------------------
// TestOrmRoundtrip — assert rows can be inserted and queried
// ---------------------------------------------------------------------------

describe('ORM round-trip CRUD', () => {
  let testUser;
  let testProduct;

  test('create and query User', async () => {
    testUser = await User.create({
      clerk_id: 'clerk_jest_001',
      email: 'jest@example.com',
      name: 'Jest User',
    });
    const fetched = await User.findOne({ where: { clerk_id: 'clerk_jest_001' } });
    expect(fetched).not.toBeNull();
    expect(fetched.email).toBe('jest@example.com');
  });

  test('create and query Product', async () => {
    testProduct = await Product.create({
      platform: 'myntra',
      platform_id: 'myntra-jest-001',
      name: 'Test Kurta',
      url: 'https://myntra.com/product/jest-001',
    });
    const fetched = await Product.findOne({ where: { platform_id: 'myntra-jest-001' } });
    expect(fetched).not.toBeNull();
    expect(fetched.platform).toBe('myntra');
  });

  test('create Alert linked to User and Product', async () => {
    const alert = await Alert.create({
      user_id: testUser.id,
      product_id: testProduct.id,
      alert_type: 'price_drop',
      target_price_inr: 999,
    });
    const fetched = await Alert.findOne({ where: { user_id: testUser.id } });
    expect(fetched).not.toBeNull();
    expect(fetched.alert_type).toBe('price_drop');
    expect(fetched.is_active).toBe(true);
  });

  test('create WardrobeItem without product link (nullable product_id)', async () => {
    const item = await WardrobeItem.create({
      user_id: testUser.id,
      product_id: null,
      name: 'My Denim Jacket',
      category: 'outerwear',
    });
    const fetched = await WardrobeItem.findOne({ where: { name: 'My Denim Jacket' } });
    expect(fetched).not.toBeNull();
    expect(fetched.product_id).toBeNull();
    expect(fetched.times_worn).toBe(0);
  });

  test('alert is_active defaults to true', async () => {
    const alert = await Alert.create({
      user_id: testUser.id,
      product_id: testProduct.id,
      alert_type: 'restock',
    });
    expect(alert.is_active).toBe(true);
    // SQLite returns undefined for unset nullable integers; PostgreSQL returns null.
    // toBeFalsy() covers both environments.
    expect(alert.target_price_inr).toBeFalsy();
  });

  test('User.clerk_id has unique constraint', async () => {
    await expect(
      User.create({ clerk_id: 'clerk_jest_001', email: 'dup@example.com' })
    ).rejects.toThrow();
  });
});
