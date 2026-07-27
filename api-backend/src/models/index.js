/**
 * Models index — api-backend.
 *
 * Import all Sequelize models here and define associations.
 * Any code that needs models imports from this single file.
 */

'use strict';

const sequelize = require('../db/connection');
const Alert = require('./Alert');
const Product = require('./Product');
const User = require('./User');
const WardrobeItem = require('./WardrobeItem');

// ---------------------------------------------------------------------------
// Associations
// ---------------------------------------------------------------------------

// User ↔ Alert (one-to-many)
User.hasMany(Alert, { foreignKey: 'user_id', onDelete: 'CASCADE' });
Alert.belongsTo(User, { foreignKey: 'user_id' });

// User ↔ WardrobeItem (one-to-many)
User.hasMany(WardrobeItem, { foreignKey: 'user_id', onDelete: 'CASCADE' });
WardrobeItem.belongsTo(User, { foreignKey: 'user_id' });

// Product ↔ Alert (one-to-many)
Product.hasMany(Alert, { foreignKey: 'product_id', onDelete: 'CASCADE' });
Alert.belongsTo(Product, { foreignKey: 'product_id' });

// Product ↔ WardrobeItem (one-to-many, nullable)
Product.hasMany(WardrobeItem, { foreignKey: 'product_id', onDelete: 'SET NULL' });
WardrobeItem.belongsTo(Product, { foreignKey: 'product_id' });

module.exports = { sequelize, Alert, Product, User, WardrobeItem };
