/**
 * Alert Service — api-backend.
 *
 * Responsibility: All business logic for price drop and restock alerts.
 *
 * Architecture rules:
 *   Layer: Service
 *   One job: Alert CRUD, price threshold evaluation, Socket.io dispatch
 *   Never does: HTTP routing, raw DB queries without models, direct Socket.io init
 *
 * Operations:
 *   createAlert      — Persist a new alert in the DB
 *   getUserAlerts    — Fetch all alerts for a user
 *   deleteAlert      — Soft-delete (is_active = false) or hard-delete alert by id
 *   checkPriceAlerts — Called by Celery beat: compare current price vs target; fire Socket event if triggered
 */

'use strict';

const Alert = require('../models/Alert');
const { emitToUser } = require('../integrations/socketManager');

const logger = {
  info: (...args) => console.log('[alert_service]', ...args),
  warn: (...args) => console.warn('[alert_service]', ...args),
  error: (...args) => console.error('[alert_service]', ...args),
};

// ---------------------------------------------------------------------------
// CRUD operations
// ---------------------------------------------------------------------------

/**
 * Create a new alert.
 *
 * @param {object} data
 * @param {string} data.user_id
 * @param {string} data.product_id
 * @param {'price_drop'|'restock'} data.alert_type
 * @param {number|null} [data.target_price_inr]
 * @returns {Promise<Alert>}
 */
async function createAlert({ user_id, product_id, alert_type, target_price_inr = null }) {
  logger.info(`createAlert user_id=${user_id} product_id=${product_id} type=${alert_type}`);

  const alert = await Alert.create({
    user_id,
    product_id,
    alert_type,
    target_price_inr: alert_type === 'price_drop' ? target_price_inr : null,
    is_active: true,
  });

  logger.info(`created alert id=${alert.id}`);
  return alert;
}

/**
 * Fetch all active + inactive alerts for a given user.
 *
 * @param {string} userId
 * @returns {Promise<Alert[]>}
 */
async function getUserAlerts(userId) {
  logger.info(`getUserAlerts userId=${userId}`);
  return Alert.findAll({
    where: { user_id: userId },
    order: [['created_at', 'DESC']],
  });
}

/**
 * Delete (hard-delete) an alert by id.
 * Returns null if alert not found.
 *
 * @param {string} alertId
 * @returns {Promise<Alert|null>}
 */
async function deleteAlert(alertId) {
  logger.info(`deleteAlert alertId=${alertId}`);
  const alert = await Alert.findByPk(alertId);
  if (!alert) {
    logger.warn(`deleteAlert: alert not found id=${alertId}`);
    return null;
  }
  await alert.destroy();
  logger.info(`deleted alert id=${alertId}`);
  return alert;
}

// ---------------------------------------------------------------------------
// Price alert evaluation (called by Celery beat job via internal HTTP or direct)
// ---------------------------------------------------------------------------

/**
 * Check all active price_drop alerts against the provided current prices map.
 * For each alert where current price ≤ target_price_inr:
 *   - Mark alert is_active = false (alert fired, prevent re-fire)
 *   - Emit 'price_drop' Socket.io event to the target user
 *
 * @param {Record<string, number>} currentPrices  Map of product_id → current_price_inr
 * @returns {Promise<{ fired: number, checked: number }>}
 */
async function checkPriceAlerts(currentPrices = {}) {
  logger.info(`checkPriceAlerts checking ${Object.keys(currentPrices).length} product prices`);

  const activeAlerts = await Alert.findAll({
    where: { alert_type: 'price_drop', is_active: true },
  });

  logger.info(`checkPriceAlerts found ${activeAlerts.length} active price_drop alerts`);

  let fired = 0;
  for (const alert of activeAlerts) {
    const currentPrice = currentPrices[alert.product_id];
    if (currentPrice === undefined) continue;

    if (currentPrice <= alert.target_price_inr) {
      // Deactivate alert to prevent repeated firing
      alert.is_active = false;
      await alert.save();

      // Emit real-time Socket.io notification to the user
      emitToUser(alert.user_id, 'price_drop', {
        alertId: alert.id,
        productId: alert.product_id,
        targetPrice: alert.target_price_inr,
        currentPrice,
      });

      logger.info(`alert fired: id=${alert.id} userId=${alert.user_id} currentPrice=${currentPrice} targetPrice=${alert.target_price_inr}`);
      fired++;
    }
  }

  return { fired, checked: activeAlerts.length };
}

/**
 * Check all active restock alerts.
 * For each product that is now in stock (present in restockedProductIds):
 *   - Mark alert is_active = false
 *   - Emit 'restock' Socket.io event to the target user
 *
 * @param {string[]} restockedProductIds  List of product_ids now back in stock
 * @returns {Promise<{ fired: number, checked: number }>}
 */
async function checkRestockAlerts(restockedProductIds = []) {
  logger.info(`checkRestockAlerts checking ${restockedProductIds.length} restocked products`);

  const activeAlerts = await Alert.findAll({
    where: { alert_type: 'restock', is_active: true },
  });

  logger.info(`checkRestockAlerts found ${activeAlerts.length} active restock alerts`);

  const restockedSet = new Set(restockedProductIds);
  let fired = 0;

  for (const alert of activeAlerts) {
    if (restockedSet.has(alert.product_id)) {
      alert.is_active = false;
      await alert.save();

      emitToUser(alert.user_id, 'restock', {
        alertId: alert.id,
        productId: alert.product_id,
      });

      logger.info(`restock alert fired: id=${alert.id} userId=${alert.user_id} productId=${alert.product_id}`);
      fired++;
    }
  }

  return { fired, checked: activeAlerts.length };
}

module.exports = {
  createAlert,
  getUserAlerts,
  deleteAlert,
  checkPriceAlerts,
  checkRestockAlerts,
};
