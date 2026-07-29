/**
 * Express Application Factory — api-backend.
 *
 * Responsibility: Create the Express app, register middleware, and mount routes.
 * This is the composition root. No logic lives here.
 *
 * Middleware order (matters for Express):
 *   1. CORS            — outermost, handles preflight OPTIONS before auth
 *   2. Request logger  — log every request before business logic
 *   3. Rate limiter    — enforce quota after logging
 *   4. Body parser     — parse JSON bodies
 *   5. Routes          — all API routes
 *   6. Error handler   — must be last (4-arg Express error handler)
 */

'use strict';

const express = require('express');

const corsMiddleware = require('./middleware/cors');
const requestLogger = require('./middleware/requestLogger');
const rateLimiter = require('./middleware/rateLimiter');
const errorHandler = require('./middleware/errorHandler');

const authRoutes = require('./routes/authRoutes');
const userRoutes = require('./routes/userRoutes');

function createApp() {
  const app = express();

  // 1. CORS
  app.use(corsMiddleware);

  // 2. Request logger
  app.use(requestLogger);

  // 3. Rate limiter
  if (process.env.TESTING !== '1') {
    app.use(rateLimiter);
  }

  // 4. Body parser
  app.use(express.json({ limit: '1mb' }));

  // 5. Health check (no auth needed)
  app.get('/health', (_req, res) => res.json({ status: 'ok', service: 'api-backend' }));

  // 6. API routes
  app.use('/auth', authRoutes);
  app.use('/users', userRoutes);

  // 7. Error handler — must be last
  app.use(errorHandler);

  return app;
}

module.exports = createApp;
