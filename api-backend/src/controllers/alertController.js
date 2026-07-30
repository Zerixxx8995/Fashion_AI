/**
 * Alert Controller — api-backend.
 *
 * Responsibility: Parse HTTP request, call alertService, shape response.
 *
 * Architecture rules:
 *   Layer: Controller
 *   One job: Request parsing → service call → response shaping
 *   Never does: DB queries, business logic, Socket.io setup
 */

'use strict';

const alertService = require('../services/alertService');

const logger = {
  info: (...args) => console.log('[alert_controller]', ...args),
  error: (...args) => console.error('[alert_controller]', ...args),
};

/**
 * POST /alerts
 * Create a new price drop or restock alert.
 */
async function createAlert(req, res, next) {
  try {
    const { user_id, product_id, alert_type, target_price_inr } = req.body;
    logger.info(`createAlert user_id=${user_id} type=${alert_type}`);

    const alert = await alertService.createAlert({
      user_id,
      product_id,
      alert_type,
      target_price_inr: target_price_inr ?? null,
    });

    return res.status(201).json({ alert });
  } catch (err) {
    next(err);
  }
}

/**
 * GET /alerts/:userId
 * Get all alerts for a user.
 */
async function getUserAlerts(req, res, next) {
  try {
    const { userId } = req.params;
    logger.info(`getUserAlerts userId=${userId}`);

    const alerts = await alertService.getUserAlerts(userId);
    return res.status(200).json({ alerts, count: alerts.length });
  } catch (err) {
    next(err);
  }
}

/**
 * DELETE /alerts/:id
 * Delete an alert by id.
 */
async function deleteAlert(req, res, next) {
  try {
    const { id } = req.params;
    logger.info(`deleteAlert id=${id}`);

    const deleted = await alertService.deleteAlert(id);
    if (!deleted) {
      return res.status(404).json({
        error: 'Not Found',
        detail: `Alert with id '${id}' not found.`,
        status_code: 404,
      });
    }

    return res.status(200).json({ message: 'Alert deleted successfully.', id });
  } catch (err) {
    next(err);
  }
}

module.exports = { createAlert, getUserAlerts, deleteAlert };
