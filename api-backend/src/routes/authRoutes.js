/**
 * Auth Routes — api-backend.
 *
 * Responsibility: URL mapping only. No logic here.
 *
 * Layer rules:
 *   - Define routes with router.METHOD(path, [...middleware], controller)
 *   - Never contain business logic or service calls
 *
 * Routes:
 *   POST /auth/sync   — sync Clerk user to PostgreSQL after sign-in
 */

'use strict';

const { Router } = require('express');
const authController = require('../controllers/authController');
const authMiddleware = require('../middleware/authMiddleware');
const { validateUserSync } = require('../validators/userValidator');

const router = Router();

/**
 * POST /auth/sync
 *
 * Requires a valid Clerk Bearer token.
 * Body: { email: string, name?: string }
 * Returns the synced user row.
 */
router.post('/sync', authMiddleware, validateUserSync, authController.syncUser);

module.exports = router;
