/**
 * Error Handler — api-backend.
 *
 * Responsibility: Catch all unhandled errors and return a consistent
 * error shape: { error, detail, status_code }
 *
 * Architecture: Express error-handling middleware (4 args: err, req, res, next).
 * Must be registered LAST in app.js, after all routes.
 */

'use strict';

const logger = require('./requestLogger').logger;

/**
 * Map HTTP status codes to short human-readable names.
 * @param {number} statusCode
 * @returns {string}
 */
function statusToErrorName(statusCode) {
  const map = {
    400: 'Bad Request',
    401: 'Unauthorized',
    403: 'Forbidden',
    404: 'Not Found',
    409: 'Conflict',
    422: 'Validation Error',
    429: 'Too Many Requests',
    500: 'Internal Server Error',
    503: 'Service Unavailable',
  };
  return map[statusCode] || `HTTP ${statusCode}`;
}

/**
 * Express error-handling middleware.
 * Catches errors thrown or passed to next(err) anywhere in the stack.
 *
 * Usage: app.use(errorHandler); — must be last middleware in app.js
 *
 * @param {Error} err
 * @param {import('express').Request} req
 * @param {import('express').Response} res
 * @param {import('express').NextFunction} next
 */
function errorHandler(err, req, res, next) { // eslint-disable-line no-unused-vars
  // Normalise status code
  const statusCode = err.status || err.statusCode || 500;
  const errorName = statusToErrorName(statusCode);
  const detail = err.message || 'An unexpected error occurred.';

  if (statusCode >= 500) {
    logger.error(`[error_handler] ${statusCode} ${req.method} ${req.path}: ${err.stack || detail}`);
  } else {
    logger.warn(`[error_handler] ${statusCode} ${req.method} ${req.path}: ${detail}`);
  }

  // Never leak stack traces to clients
  return res.status(statusCode).json({
    error: errorName,
    detail,
    status_code: statusCode,
  });
}

module.exports = errorHandler;
