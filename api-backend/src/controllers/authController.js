/**
 * Auth Controller — api-backend.
 *
 * Responsibility: Parse request → call authService → shape HTTP response.
 * One function per route. No business logic here.
 *
 * Routes handled:
 *   POST /auth/sync  →  syncUser
 */

'use strict';

const authService = require('../services/authService');
const { logger } = require('../middleware/requestLogger');


/**
 * POST /auth/sync
 *
 * Syncs the authenticated Clerk user into PostgreSQL.
 * The clerk_id is extracted from the verified JWT (req.auth.sub).
 * email and name come from the request body (sent by mobile after sign-in).
 *
 * Returns 200 on existing user, 201 on new user creation.
 */
async function syncUser(req, res, next) {
  try {
    const clerk_id = req.auth?.sub;     // From Clerk JWT claims
    const { email, name } = req.body;

    if (!clerk_id) {
      return res.status(401).json({
        error: 'Unauthorized',
        detail: 'JWT is missing sub claim. Ensure a valid Clerk token is provided.',
        status_code: 401,
      });
    }

    const { user, created } = await authService.syncUser({ clerk_id, email, name });

    logger.info(`[auth_controller] syncUser clerk_id=${clerk_id} created=${created}`);

    return res.status(created ? 201 : 200).json({
      message: created ? 'User created.' : 'User synced.',
      user,
    });
  } catch (err) {
    next(err);
  }
}


module.exports = { syncUser };
