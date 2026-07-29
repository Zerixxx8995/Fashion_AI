/**
 * Rate Limiter — api-backend.
 *
 * Responsibility: Per-IP sliding window rate limiting (NF8).
 * Uses express-rate-limit (no Redis required for single Render instance).
 *
 * Environment variables:
 *   RATE_LIMIT_MAX_REQUESTS    — max requests per window (default: 60)
 *   RATE_LIMIT_WINDOW_SECONDS  — window size in seconds (default: 60)
 */

'use strict';

const rateLimit = require('express-rate-limit');
const { logger } = require('./requestLogger');

const MAX_REQUESTS = parseInt(process.env.RATE_LIMIT_MAX_REQUESTS || '60', 10);
const WINDOW_SECONDS = parseInt(process.env.RATE_LIMIT_WINDOW_SECONDS || '60', 10);

const rateLimiter = rateLimit({
  windowMs: WINDOW_SECONDS * 1000,
  max: MAX_REQUESTS,
  standardHeaders: true,   // Return RateLimit-* headers (RFC 6585)
  legacyHeaders: false,
  skipSuccessfulRequests: false,

  // Canonical error shape (NF6)
  handler: (req, res) => {
    const retryAfter = Math.ceil(WINDOW_SECONDS);
    logger.warn(`[rate_limiter] 429 Too Many Requests ip=${req.ip} path=${req.path}`);
    res.status(429).json({
      error: 'Too Many Requests',
      detail: `Rate limit exceeded: ${MAX_REQUESTS} requests per ${WINDOW_SECONDS}s. Retry after ${retryAfter}s.`,
      status_code: 429,
    });
  },
});

logger.info(`[rate_limiter] configured: ${MAX_REQUESTS} req / ${WINDOW_SECONDS}s window`);

module.exports = rateLimiter;
