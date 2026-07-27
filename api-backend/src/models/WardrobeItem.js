/**
 * WardrobeItem Sequelize model — api-backend.
 *
 * Maps to the `wardrobe_items` table.
 * Indexed fields: user_id.
 *
 * product_id is nullable — items can be added without a platform product link.
 * image_url points to Backblaze B2 — user-uploaded wardrobe photos only.
 */

'use strict';

const { DataTypes } = require('sequelize');
const sequelize = require('../db/connection');

const WardrobeItem = sequelize.define(
  'WardrobeItem',
  {
    id: {
      type: DataTypes.UUID,
      defaultValue: DataTypes.UUIDV4,
      primaryKey: true,
    },
    user_id: {
      type: DataTypes.UUID,
      allowNull: false,
    },
    // Nullable: item may not be linked to a scraped product
    product_id: {
      type: DataTypes.UUID,
      allowNull: true,
    },
    name: {
      type: DataTypes.STRING(256),
      allowNull: false,
    },
    category: {
      type: DataTypes.STRING(128),
      allowNull: true,
    },
    color: {
      type: DataTypes.STRING(64),
      allowNull: true,
    },
    // Backblaze B2 URL — user uploaded this photo
    image_url: {
      type: DataTypes.TEXT,
      allowNull: true,
    },
    purchase_price_inr: {
      type: DataTypes.INTEGER,
      allowNull: true,
    },
    times_worn: {
      type: DataTypes.INTEGER,
      allowNull: false,
      defaultValue: 0,
    },
  },
  {
    tableName: 'wardrobe_items',
    timestamps: true,
    createdAt: 'added_at',
    updatedAt: false,
    indexes: [
      { fields: ['user_id'], name: 'ix_wardrobe_items_user_id' },
    ],
  }
);

module.exports = WardrobeItem;
