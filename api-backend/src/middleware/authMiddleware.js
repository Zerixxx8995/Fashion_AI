/**
 * Auth Middleware — api-backend.
 *
 * Responsibility: Verify Clerk JWT on all protected routes.
 * Attaches decoded claims to req.auth for downstream use.
 *
 * Architecture rules:
 *   One job: Is this request authenticated? (who you are)
 *   Never does: Authorisation (what you're allowed — that's in controllers)
 *
 * Strategy:
 *   Uses @clerk/express verifyToken() to validate the Bearer token.
 *   Public routes (listed in PUBLIC_PATHS) are bypassed.
 *
 * Environment variables:
 *   CLERK_SECRET_KEY     — Clerk secret key (required)
 *   CLERK_JWT_ISSUER     — Clerk frontend API URL (for JWT verification)
 */

'use strict';

const { logger } = require('./requestLogger');

// ---------------------------------------------------------------------------
// Public paths — no auth required
// ---------------------------------------------------------------------------

const PUBLIC_PATHS = new Set([
  '/health',
  '/api/health',
]);

function isPublic(path) {
  return PUBLIC_PATHS.has(path) || path.startsWith('/docs');
}

// ---------------------------------------------------------------------------
// Token verification
// ---------------------------------------------------------------------------

/**
 * Verify a Clerk JWT using the Clerk SDK.
 * Returns decoded claims on success, null on failure.
 *
 * @param {string} token
 * @returns {Promise<object|null>}
 */
async function verifyClerkToken(token) {
  try {
    const { verifyToken } = await import('@clerk/clerk-sdk-node');
    const secretKey = process.env.CLERK_SECRET_KEY;
    if (!secretKey) {
      logger.error('[auth_middleware] CLERK_SECRET_KEY not set');
      return null;
    }
    const claims = await verifyToken(token, { secretKey });
    return claims;
  } catch (err) {
    logger.warn(`[auth_middleware] token verification failed: ${err.message}`);
    return null;
  }
}

// ---------------------------------------------------------------------------
// Middleware
// ---------------------------------------------------------------------------

/**
 * Clerk JWT auth middleware for Express.
 *
 * @param {import('express').Request} req
 * @param {import('express').Response} res
 * @param {import('express').NextFunction} next
 */
async function authMiddleware(req, res, next) {
  if (isPublic(req.path)) return next();

  const authHeader = req.headers.authorization || '';
  if (!authHeader.startsWith('Bearer ')) {
    return res.status(401).json({
      error: 'Unauthorized',
      detail: "Missing or malformed Authorization header. Expected: 'Bearer <token>'",
      status_code: 401,
    });
  }

  const token = authHeader.replace(/^Bearer\s+/, '').trim();
  const claims = await verifyClerkToken(token);

  if (!claims) {
    return res.status(401).json({
      error: 'Unauthorized',
      detail: 'Invalid or expired JWT. Please sign in again.',
      status_code: 401,
    });
  }

  req.auth = claims;
  return next();
}

module.exports = authMiddleware;
