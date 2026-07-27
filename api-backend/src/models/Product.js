/**
 * Product Sequelize model — api-backend.
 *
 * Maps to the `products` table.
 * Indexed fields: platform, platform_id.
 *
 * stock_image_urls is a JSON array of URLs — raw bytes are NEVER stored.
 * CLIP embeddings live in Pinecone, not here.
 */

'use strict';

const { DataTypes } = require('sequelize');
const sequelize = require('../db/connection');

const Product = sequelize.define(
  'Product',
  {
    id: {
      type: DataTypes.UUID,
      defaultValue: DataTypes.UUIDV4,
      primaryKey: true,
    },
    // One of: myntra | amazon | flipkart | meesho | ajio
    platform: {
      type: DataTypes.STRING(32),
      allowNull: false,
    },
    platform_id: {
      type: DataTypes.STRING(256),
      allowNull: false,
    },
    name: {
      type: DataTypes.STRING(512),
      allowNull: false,
    },
    brand: {
      type: DataTypes.STRING(256),
      allowNull: true,
    },
    price_inr: {
      type: DataTypes.INTEGER,
      allowNull: true,
    },
    // JSON array of stock image URLs
    stock_image_urls: {
      type: DataTypes.JSON,
      allowNull: true,
    },
    category: {
      type: DataTypes.STRING(128),
      allowNull: true,
    },
    url: {
      type: DataTypes.TEXT,
      allowNull: false,
    },
    seller_id: {
      type: DataTypes.STRING(256),
      allowNull: true,
    },
    scraped_at: {
      type: DataTypes.DATE,
      allowNull: false,
      defaultValue: DataTypes.NOW,
    },
  },
  {
    tableName: 'products',
    timestamps: false,
    indexes: [
      { fields: ['platform'], name: 'ix_products_platform' },
      { fields: ['platform_id'], name: 'ix_products_platform_id' },
    ],
  }
);

module.exports = Product;
