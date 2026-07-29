/**
 * User Validator Middleware — api-backend.
 *
 * Responsibility: Validate input for user profile sync and update.
 * Returns consistent 422 error shape if validation fails.
 */

'use strict';

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Validate POST /auth/sync request body.
 *
 * Note: clerk_id is extracted from the Clerk JWT (req.auth.sub) by the
 * controller — it is NOT required in the request body. Only email (required)
 * and name (optional) are validated here.
 */
function validateUserSync(req, res, next) {
  const { email, name } = req.body;

  if (!email || !EMAIL_REGEX.test(email)) {
    return res.status(422).json({
      error: 'Validation Error',
      detail: 'email must be a valid email address.',
      status_code: 422,
    });
  }

  if (name !== undefined && (typeof name !== 'string' || name.trim() === '')) {
    return res.status(422).json({
      error: 'Validation Error',
      detail: 'name must be a non-empty string.',
      status_code: 422,
    });
  }

  next();
}


/**
 * Validate PUT /users/:id/profile request body and params
 */
function validateUserProfileUpdate(req, res, next) {
  const { id } = req.params;
  const { body_type, height_cm, weight_kg, measurements, style_preferences, skin_tone } = req.body;

  // Validate URL param ID is UUID
  if (!UUID_REGEX.test(id)) {
    return res.status(422).json({
      error: 'Validation Error',
      detail: "Param 'id' must be a valid UUID.",
      status_code: 422,
    });
  }

  // Validate body_type
  if (body_type !== undefined && (typeof body_type !== 'string' || body_type.trim() === '')) {
    return res.status(422).json({
      error: 'Validation Error',
      detail: 'body_type must be a non-empty string.',
      status_code: 422,
    });
  }

  // Validate height
  if (height_cm !== undefined) {
    const val = Number(height_cm);
    if (!Number.isInteger(val) || val <= 0) {
      return res.status(422).json({
        error: 'Validation Error',
        detail: 'height_cm must be a positive integer.',
        status_code: 422,
      });
    }
  }

  // Validate weight
  if (weight_kg !== undefined) {
    const val = Number(weight_kg);
    if (!Number.isInteger(val) || val <= 0) {
      return res.status(422).json({
        error: 'Validation Error',
        detail: 'weight_kg must be a positive integer.',
        status_code: 422,
      });
    }
  }

  // Validate measurements (must be an object containing chest, waist, hips if provided)
  if (measurements !== undefined) {
    if (typeof measurements !== 'object' || measurements === null || Array.isArray(measurements)) {
      return res.status(422).json({
        error: 'Validation Error',
        detail: 'measurements must be a JSON object.',
        status_code: 422,
      });
    }

    const { chest, waist, hips } = measurements;
    if (chest !== undefined && (typeof chest !== 'number' || chest <= 0)) {
      return res.status(422).json({
        error: 'Validation Error',
        detail: 'chest measurement must be a positive number.',
        status_code: 422,
      });
    }
    if (waist !== undefined && (typeof waist !== 'number' || waist <= 0)) {
      return res.status(422).json({
        error: 'Validation Error',
        detail: 'waist measurement must be a positive number.',
        status_code: 422,
      });
    }
    if (hips !== undefined && (typeof hips !== 'number' || hips <= 0)) {
      return res.status(422).json({
        error: 'Validation Error',
        detail: 'hips measurement must be a positive number.',
        status_code: 422,
      });
    }
  }

  // Validate style_preferences (must be array of strings)
  if (style_preferences !== undefined) {
    if (!Array.isArray(style_preferences)) {
      return res.status(422).json({
        error: 'Validation Error',
        detail: 'style_preferences must be an array.',
        status_code: 422,
      });
    }
    for (const pref of style_preferences) {
      if (typeof pref !== 'string' || pref.trim() === '') {
        return res.status(422).json({
          error: 'Validation Error',
          detail: 'style_preferences must only contain non-empty strings.',
          status_code: 422,
        });
      }
    }
  }

  // Validate skin_tone
  if (skin_tone !== undefined && (typeof skin_tone !== 'string' || skin_tone.trim() === '')) {
    return res.status(422).json({
      error: 'Validation Error',
      detail: 'skin_tone must be a non-empty string.',
      status_code: 422,
    });
  }

  next();
}

module.exports = {
  validateUserSync,
  validateUserProfileUpdate,
};
