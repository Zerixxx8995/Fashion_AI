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
const alertRoutes = require('./routes/alertRoutes');
const internalAlertRoutes = require('./routes/internalAlertRoutes');
const wardrobeRoutes = require('./routes/wardrobeRoutes');
const sequelize = require('./db/connection');

/**
 * Execute query to check database size and log a warning if it exceeds 400MB.
 */
async function checkDatabaseSize() {
  if (process.env.TESTING === '1' || sequelize.options.dialect !== 'postgres') {
    return;
  }
  try {
    const databaseName = sequelize.config.database;
    const [results] = await sequelize.query(`SELECT pg_database_size('${databaseName}') AS size_bytes;`);
    if (results && results.length > 0) {
      const sizeBytes = parseInt(results[0].size_bytes, 10);
      const sizeMB = sizeBytes / (1024 * 1024);
      if (sizeMB > 400) {
        console.warn(`[database_check] WARNING: Neon PostgreSQL database size is high! Current size: ${sizeMB.toFixed(2)} MB (Limit: 500 MB)`);
      } else {
        console.log(`[database_check] Database size check: ${sizeMB.toFixed(2)} MB`);
      }
    }
  } catch (err) {
    console.error(`[database_check] Failed to check database size: ${err.message}`);
  }
}

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
  app.use('/alerts', alertRoutes);
  app.use('/internal', internalAlertRoutes);
  app.use('/wardrobe', wardrobeRoutes);

  // 7. Error handler — must be last
  app.use(errorHandler);

  // Run DB size check asynchronously
  checkDatabaseSize();

  return app;
}

// Start server if run directly
if (require.main === module) {
  const PORT = process.env.PORT || 3000;
  const { initSocket } = require('./integrations/socketManager');
  const app = createApp();
  sequelize.sync().then(() => {
    const server = app.listen(PORT, () => {
      console.log(`[server] Server listening on port ${PORT}`);
    });
    // Attach Socket.io to the running HTTP server so WebSocket connections work
    initSocket(server);
  }).catch((err) => {
    console.error('[server] Failed to sync database on startup:', err);
  });
}

module.exports = createApp;
