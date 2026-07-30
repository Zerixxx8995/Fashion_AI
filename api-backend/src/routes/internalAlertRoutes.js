/**
 * Internal Alerts Router — api-backend.
 *
 * Responsibility: Expose internal HTTP endpoints consumed ONLY by the
 * ml-backend Celery jobs (not by the mobile client).
 *
 * Security:
 *   All routes here validate the X-Internal-Secret header against
 *   process.env.INTERNAL_API_SECRET.  No Clerk JWT required.
 *
 * Routes:
 *   POST /internal/alerts/check-prices   — Receive current product prices from Celery,
 *                                          evaluate thresholds, fire Socket.io events
 *   POST /internal/alerts/check-restock  — Receive restocked product IDs from Celery,
 *                                          fire restock Socket.io events
 */

'use strict';

const express = require('express');
const router = express.Router();
const alertService = require('../services/alertService');

const logger = {
  info: (...args) => console.log('[internal_alerts]', ...args),
  warn: (...args) => console.warn('[internal_alerts]', ...args),
  error: (...args) => console.error('[internal_alerts]', ...args),
};

// ---------------------------------------------------------------------------
// Shared internal auth middleware
// ---------------------------------------------------------------------------

function internalAuth(req, res, next) {
  const secret = req.headers['x-internal-secret'];
  const expected = process.env.INTERNAL_API_SECRET || 'dev-internal-secret';

  if (!secret || secret !== expected) {
    logger.warn(`internalAuth: unauthorized attempt from ${req.ip}`);
    return res.status(401).json({
      error: 'Unauthorized',
      detail: 'Missing or invalid X-Internal-Secret header.',
      status_code: 401,
    });
  }
  next();
}

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------

/**
 * POST /internal/alerts/check-prices
 * Body: { prices: { [product_id]: price_inr } }
 */
router.post('/check-prices', internalAuth, async (req, res, next) => {
  try {
    const { prices = {} } = req.body;
    logger.info(`check-prices: evaluating ${Object.keys(prices).length} products`);

    const result = await alertService.checkPriceAlerts(prices);
    return res.status(200).json({ status: 'ok', ...result });
  } catch (err) {
    next(err);
  }
});

/**
 * POST /internal/alerts/check-restock
 * Body: { restocked_product_ids: string[] }
 */
router.post('/check-restock', internalAuth, async (req, res, next) => {
  try {
    const { restocked_product_ids = [] } = req.body;
    logger.info(`check-restock: ${restocked_product_ids.length} products restocked`);

    const result = await alertService.checkRestockAlerts(restocked_product_ids);
    return res.status(200).json({ status: 'ok', ...result });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
