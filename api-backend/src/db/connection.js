/**
 * PostgreSQL connection via Sequelize — api-backend.
 *
 * Responsibility: export a configured Sequelize instance. Nothing else.
 *
 * DATABASE_URL is read from process.env — never hardcoded.
 * In tests, the DATABASE_URL is set to a SQLite in-memory URL for isolation.
 */

'use strict';

const { Sequelize } = require('sequelize');

const DATABASE_URL = process.env.DATABASE_URL || 'sqlite::memory:';

const sequelize = new Sequelize(DATABASE_URL, {
  dialect: DATABASE_URL.startsWith('sqlite') ? 'sqlite' : 'postgres',
  logging: false,       // Set to console.log to see all SQL
  pool: {
    max: 10,
    min: 0,
    acquire: 30000,
    idle: 10000,
  },
  dialectOptions: DATABASE_URL.startsWith('postgres')
    ? { ssl: { require: true, rejectUnauthorized: false } }
    : {},
});

module.exports = sequelize;
