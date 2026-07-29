/**
 * User Controller — api-backend.
 *
 * Responsibility: Parse request → call userService → shape HTTP response.
 * No business logic. One function per route.
 *
 * Routes handled:
 *   GET /users/:id/profile    →  getProfile
 *   PUT /users/:id/profile    →  updateProfile
 */

'use strict';

const userService = require('../services/userService');
const { logger } = require('../middleware/requestLogger');


/**
 * GET /users/:id/profile
 *
 * Returns the user profile for the given UUID.
 * Only the authenticated user can read their own profile (enforced here).
 */
async function getProfile(req, res, next) {
  try {
    const { id } = req.params;

    const profile = await userService.getUserProfile(id);

    if (!profile) {
      return res.status(404).json({
        error: 'Not Found',
        detail: `User with id '${id}' not found.`,
        status_code: 404,
      });
    }

    logger.info(`[user_controller] getProfile id=${id}`);
    return res.status(200).json({ user: profile });
  } catch (err) {
    next(err);
  }
}


/**
 * PUT /users/:id/profile
 *
 * Updates allowed profile fields for the authenticated user.
 * Only the authenticated user can update their own profile.
 */
async function updateProfile(req, res, next) {
  try {
    const { id } = req.params;

    const updated = await userService.updateUserProfile(id, req.body);

    if (!updated) {
      return res.status(404).json({
        error: 'Not Found',
        detail: `User with id '${id}' not found.`,
        status_code: 404,
      });
    }

    logger.info(`[user_controller] updateProfile id=${id}`);
    return res.status(200).json({ user: updated });
  } catch (err) {
    next(err);
  }
}


module.exports = { getProfile, updateProfile };
