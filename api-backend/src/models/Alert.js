/**
 * Alert Sequelize model — api-backend.
 *
 * Maps to the `alerts` table.
 * Indexed fields: user_id.
 *
 * alert_type: 'price_drop' | 'restock'
 * target_price_inr: only set for price_drop alerts.
 * is_active: Celery beat queries WHERE is_active = true to find live alerts.
 */

'use strict';

const { DataTypes } = require('sequelize');
const sequelize = require('../db/connection');

const Alert = sequelize.define(
  'Alert',
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
    product_id: {
      type: DataTypes.UUID,
      allowNull: false,
    },
    // 'price_drop' or 'restock'
    alert_type: {
      type: DataTypes.STRING(32),
      allowNull: false,
    },
    // Only used for price_drop alerts
    target_price_inr: {
      type: DataTypes.INTEGER,
      allowNull: true,
    },
    is_active: {
      type: DataTypes.BOOLEAN,
      allowNull: false,
      defaultValue: true,
    },
  },
  {
    tableName: 'alerts',
    timestamps: true,
    createdAt: 'created_at',
    updatedAt: false,
    indexes: [
      { fields: ['user_id'], name: 'ix_alerts_user_id' },
    ],
  }
);

module.exports = Alert;
