/**
 * User Service — api-backend.
 *
 * Responsibility: Business logic for fetching and updating user profiles.
 *
 * Layer rules:
 *   One job: read/update User rows — no HTTP, no auth logic
 *   Called by: userController.js
 */

'use strict';

const User = require('../models/User');
const { logger } = require('../middleware/requestLogger');


/**
 * Get a user profile by internal UUID.
 *
 * @param {string} id  Internal UUID (primary key)
 * @returns {Promise<object|null>}
 */
async function getUserProfile(id) {
  const user = await User.findByPk(id);
  return user ? user.toJSON() : null;
}


/**
 * Update allowed profile fields for a user.
 *
 * Only updates fields that are explicitly provided in `updates`.
 * Silently ignores unknown fields (whitelist approach).
 *
 * Allowed fields: body_type, height_cm, weight_kg, measurements,
 *                 style_preferences, skin_tone
 *
 * @param {string} id       Internal UUID
 * @param {object} updates  Partial user object with fields to update
 * @returns {Promise<object|null>}  Updated user row, or null if not found
 */
async function updateUserProfile(id, updates) {
  const ALLOWED_FIELDS = [
    'body_type', 'height_cm', 'weight_kg',
    'measurements', 'style_preferences', 'skin_tone',
  ];

  const user = await User.findByPk(id);
  if (!user) return null;

  const sanitised = {};
  for (const field of ALLOWED_FIELDS) {
    if (updates[field] !== undefined) {
      sanitised[field] = updates[field];
    }
  }

  if (Object.keys(sanitised).length === 0) {
    return user.toJSON();   // Nothing to update — return current state
  }

  await user.update(sanitised);
  logger.info(`[user_service] updateUserProfile id=${id} fields=${Object.keys(sanitised).join(',')}`);
  return user.toJSON();
}


module.exports = { getUserProfile, updateUserProfile };
