/**
 * User Routes — api-backend.
 *
 * Responsibility: URL mapping only. No logic.
 *
 * Routes:
 *   GET /users/:id/profile   — get user profile
 *   PUT /users/:id/profile   — update user profile
 */

'use strict';

const { Router } = require('express');
const userController = require('../controllers/userController');
const authMiddleware = require('../middleware/authMiddleware');
const { validateUserProfileUpdate } = require('../validators/userValidator');

const router = Router();

/**
 * GET /users/:id/profile
 * Requires valid Clerk Bearer token.
 */
router.get('/:id/profile', authMiddleware, userController.getProfile);

/**
 * PUT /users/:id/profile
 * Requires valid Clerk Bearer token.
 * Validates body fields via validateUserProfileUpdate.
 */
router.put('/:id/profile', authMiddleware, validateUserProfileUpdate, userController.updateProfile);

module.exports = router;
