/**
 * Auth Service — api-backend.
 *
 * Responsibility: Business logic for Clerk user sync and lookup.
 * Syncs a Clerk user into the PostgreSQL `users` table on first login.
 *
 * Layer rules:
 *   One job: upsert User row from Clerk claims, find user by clerk_id
 *   Never does: HTTP knowledge, JWT verification, response shaping
 *
 * Called by: authController.js
 */

'use strict';

const User = require('../models/User');
const { logger } = require('../middleware/requestLogger');


/**
 * Sync a Clerk user to PostgreSQL on first login (upsert by clerk_id).
 *
 * Called after JWT is verified by authMiddleware. The Clerk user_id is
 * extracted from the JWT claims (req.auth.sub) and used as clerk_id.
 *
 * @param {{ clerk_id: string, email: string, name?: string }} data
 * @returns {Promise<{ user: object, created: boolean }>}
 */
async function syncUser({ clerk_id, email, name }) {
  const [user, created] = await User.findOrCreate({
    where: { clerk_id },
    defaults: {
      clerk_id,
      email,
      name: name || null,
    },
  });

  if (!created && user.email !== email) {
    // Email may have changed in Clerk — keep in sync
    await user.update({ email });
  }

  logger.info(`[auth_service] syncUser clerk_id=${clerk_id} created=${created}`);
  return { user: user.toJSON(), created };
}


/**
 * Find a User row by their internal UUID (primary key).
 *
 * @param {string} id  Internal UUID (primary key)
 * @returns {Promise<object|null>}  User row or null if not found
 */
async function getUserById(id) {
  const user = await User.findByPk(id);
  return user ? user.toJSON() : null;
}


/**
 * Find a User row by Clerk user_id (clerk_id column).
 *
 * @param {string} clerkId  Clerk user_id from JWT sub claim
 * @returns {Promise<object|null>}
 */
async function getUserByClerkId(clerkId) {
  const user = await User.findOne({ where: { clerk_id: clerkId } });
  return user ? user.toJSON() : null;
}


module.exports = { syncUser, getUserById, getUserByClerkId };
