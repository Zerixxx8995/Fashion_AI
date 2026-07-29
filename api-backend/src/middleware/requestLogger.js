/**
 * Request Logger — api-backend.
 *
 * Responsibility: Log every inbound request and outbound response
 * with method, path, status code, and duration.
 *
 * Architecture: Express middleware + a shared `logger` export.
 * Other modules (errorHandler, authMiddleware) import `logger` from here
 * so all logs go through one formatter.
 */

'use strict';

/** Minimal structured logger using console (no extra deps). */
const logger = {
  info:  (...args) => console.log(`[INFO]  ${new Date().toISOString()}`, ...args),
  warn:  (...args) => console.warn(`[WARN]  ${new Date().toISOString()}`, ...args),
  error: (...args) => console.error(`[ERROR] ${new Date().toISOString()}`, ...args),
  debug: (...args) => {
    if (process.env.LOG_LEVEL === 'debug') {
      console.log(`[DEBUG] ${new Date().toISOString()}`, ...args);
    }
  },
};

/**
 * Express request logger middleware.
 * Logs → → METHOD /path on request start.
 * Logs ← ← METHOD /path STATUS Xms on response finish.
 *
 * @param {import('express').Request} req
 * @param {import('express').Response} res
 * @param {import('express').NextFunction} next
 */
function requestLogger(req, res, next) {
  const start = Date.now();
  logger.info(`→ → ${req.method} ${req.path}`);

  res.on('finish', () => {
    const duration = Date.now() - start;
    const logFn = res.statusCode >= 400 ? logger.warn : logger.info;
    logFn(`← ← ${req.method} ${req.path} ${res.statusCode} ${duration}ms`);
  });

  next();
}

module.exports = requestLogger;
module.exports.logger = logger;
