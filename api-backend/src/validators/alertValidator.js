/**
 * Alert Validator Middleware — api-backend.
 *
 * Responsibility: Validate input for price drop and restock alert creation.
 * Returns consistent 422 error shape if validation fails.
 */

'use strict';

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Validate POST /alerts request body
 */
function validateAlertCreate(req, res, next) {
  const { user_id, product_id, alert_type, target_price_inr } = req.body;

  // Validate user_id
  if (!user_id || !UUID_REGEX.test(user_id)) {
    return res.status(422).json({
      error: 'Validation Error',
      detail: 'user_id must be a valid UUID.',
      status_code: 422,
    });
  }

  // Validate product_id
  if (!product_id || !UUID_REGEX.test(product_id)) {
    return res.status(422).json({
      error: 'Validation Error',
      detail: 'product_id must be a valid UUID.',
      status_code: 422,
    });
  }

  // Validate alert_type
  if (!alert_type || (alert_type !== 'price_drop' && alert_type !== 'restock')) {
    return res.status(422).json({
      error: 'Validation Error',
      detail: "alert_type must be either 'price_drop' or 'restock'.",
      status_code: 422,
    });
  }

  // Validate target_price_inr
  if (alert_type === 'price_drop') {
    if (target_price_inr === undefined || target_price_inr === null) {
      return res.status(422).json({
        error: 'Validation Error',
        detail: "target_price_inr is required when alert_type is 'price_drop'.",
        status_code: 422,
      });
    }

    const val = Number(target_price_inr);
    if (!Number.isInteger(val) || val <= 0) {
      return res.status(422).json({
        error: 'Validation Error',
        detail: 'target_price_inr must be a positive integer.',
        status_code: 422,
      });
    }
  } else {
    // alert_type === 'restock', target_price_inr should not be provided or should be null
    if (target_price_inr !== undefined && target_price_inr !== null) {
      return res.status(422).json({
        error: 'Validation Error',
        detail: "target_price_inr must not be set for 'restock' alerts.",
        status_code: 422,
      });
    }
  }

  next();
}

/**
 * Validate DELETE /alerts/:id or GET /alerts/:userId params
 */
function validateAlertParams(req, res, next) {
  const { id, userId } = req.params;

  if (id !== undefined && !UUID_REGEX.test(id)) {
    return res.status(422).json({
      error: 'Validation Error',
      detail: "Param 'id' must be a valid UUID.",
      status_code: 422,
    });
  }

  if (userId !== undefined && !UUID_REGEX.test(userId)) {
    return res.status(422).json({
      error: 'Validation Error',
      detail: "Param 'userId' must be a valid UUID.",
      status_code: 422,
    });
  }

  next();
}

module.exports = {
  validateAlertCreate,
  validateAlertParams,
};
