/**
 * User Sequelize model — api-backend.
 *
 * Maps to the `users` table.
 * Indexed fields: clerk_id (unique index for auth lookups).
 *
 * clerk_id is synced from Clerk via webhook on user.created event.
 * All auth-gated routes resolve the User row by clerk_id from the JWT.
 */

'use strict';

const { DataTypes } = require('sequelize');
const sequelize = require('../db/connection');

const User = sequelize.define(
  'User',
  {
    id: {
      type: DataTypes.UUID,
      defaultValue: DataTypes.UUIDV4,
      primaryKey: true,
    },
    clerk_id: {
      type: DataTypes.STRING(128),
      allowNull: false,
      unique: true,       // Enforces uniqueness and creates a DB index
    },
    email: {
      type: DataTypes.STRING(320),
      allowNull: false,
    },
    name: {
      type: DataTypes.STRING(256),
      allowNull: true,
    },
    body_type: {
      type: DataTypes.STRING(64),
      allowNull: true,
    },
    height_cm: {
      type: DataTypes.INTEGER,
      allowNull: true,
    },
    weight_kg: {
      type: DataTypes.INTEGER,
      allowNull: true,
    },
    // JSON object: {"chest": 90, "waist": 75, "hips": 95}
    measurements: {
      type: DataTypes.JSON,
      allowNull: true,
    },
    // JSON array: ["casual", "streetwear"]
    style_preferences: {
      type: DataTypes.JSON,
      allowNull: true,
    },
    skin_tone: {
      type: DataTypes.STRING(64),
      allowNull: true,
    },
  },
  {
    tableName: 'users',
    timestamps: true,
    createdAt: 'created_at',
    updatedAt: false,
    indexes: [
      // Explicit index declaration (in addition to unique: true above)
      // for clarity in migration output and test assertions.
      { fields: ['clerk_id'], name: 'ix_users_clerk_id' },
    ],
  }
);

module.exports = User;
