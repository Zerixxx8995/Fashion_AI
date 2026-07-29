/**
 * CORS Configuration — api-backend.
 *
 * Responsibility: Configure CORS headers for the Node.js Express backend.
 *
 * Strategy:
 *   Development: allow all origins (*)
 *   Production:  restrict to ALLOWED_ORIGINS env var (comma-separated list)
 *
 * Environment variables:
 *   ALLOWED_ORIGINS — comma-separated allowed origins.
 *                     Defaults to '*' if not set.
 */

'use strict';

const cors = require('cors');
const { logger } = require('./requestLogger');

function getAllowedOrigins() {
  const raw = (process.env.ALLOWED_ORIGINS || '').trim();
  if (!raw) {
    logger.warn('[cors] ALLOWED_ORIGINS not set — allowing all origins (*). Set in production.');
    return '*';
  }
  const origins = raw.split(',').map((o) => o.trim()).filter(Boolean);
  logger.info(`[cors] allowed origins: ${origins.join(', ')}`);
  return origins;
}

const corsMiddleware = cors({
  origin: getAllowedOrigins(),
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  exposedHeaders: ['X-Response-Time-Ms'],
});

module.exports = corsMiddleware;
