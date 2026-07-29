/**
 * Input Validator — api-backend.
 *
 * Responsibility: Reusable express-validator wrappers that validate
 * request body / param / query fields and return 422 with a consistent
 * error shape on failure (NF5, NF6).
 *
 * Usage:
 *   const { validateResult } = require('../middleware/inputValidator');
 *   router.post('/route', [body('field').notEmpty()], validateResult, controller);
 */

'use strict';

const { validationResult } = require('express-validator');
const { logger } = require('./requestLogger');

/**
 * Middleware that reads express-validator results.
 * If errors exist → returns 422 with canonical error shape.
 * If clean → calls next().
 *
 * @param {import('express').Request} req
 * @param {import('express').Response} res
 * @param {import('express').NextFunction} next
 */
function validateResult(req, res, next) {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    const detail = errors
      .array()
      .map((e) => `${e.path}: ${e.msg}`)
      .join('; ');

    logger.warn(`[input_validator] 422 ${req.method} ${req.path}: ${detail}`);

    return res.status(422).json({
      error: 'Validation Error',
      detail,
      status_code: 422,
    });
  }
  return next();
}

module.exports = { validateResult };
