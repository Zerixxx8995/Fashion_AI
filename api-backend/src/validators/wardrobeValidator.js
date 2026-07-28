/**
 * Wardrobe Validator Middleware — api-backend.
 *
 * Responsibility: Validate input for wardrobe item creation and parameters.
 * Returns consistent 422 error shape if validation fails.
 */

'use strict';

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const URL_REGEX = /^https?:\/\/[^\s/$.?#].[^\s]*$/i;

/**
 * Validate POST /wardrobe request body
 */
function validateWardrobeCreate(req, res, next) {
  const { user_id, product_id, name, category, color, image_url, purchase_price_inr, times_worn } = req.body;

  // Validate user_id
  if (!user_id || !UUID_REGEX.test(user_id)) {
    return res.status(422).json({
      error: 'Validation Error',
      detail: 'user_id must be a valid UUID.',
      status_code: 422,
    });
  }

  // Validate product_id (optional, nullable)
  if (product_id !== undefined && product_id !== null) {
    if (!UUID_REGEX.test(product_id)) {
      return res.status(422).json({
        error: 'Validation Error',
        detail: 'product_id must be a valid UUID or null.',
        status_code: 422,
      });
    }
  }

  // Validate name
  if (!name || typeof name !== 'string' || name.trim() === '') {
    return res.status(422).json({
      error: 'Validation Error',
      detail: 'name must be a non-empty string.',
      status_code: 422,
    });
  }

  // Validate category
  if (category !== undefined && (typeof category !== 'string' || category.trim() === '')) {
    return res.status(422).json({
      error: 'Validation Error',
      detail: 'category must be a non-empty string.',
      status_code: 422,
    });
  }

  // Validate color
  if (color !== undefined && (typeof color !== 'string' || color.trim() === '')) {
    return res.status(422).json({
      error: 'Validation Error',
      detail: 'color must be a non-empty string.',
      status_code: 422,
    });
  }

  // Validate image_url
  if (image_url !== undefined && image_url !== null) {
    if (typeof image_url !== 'string' || !URL_REGEX.test(image_url)) {
      return res.status(422).json({
        error: 'Validation Error',
        detail: 'image_url must be a valid HTTP/HTTPS URL.',
        status_code: 422,
      });
    }
  }

  // Validate purchase_price_inr
  if (purchase_price_inr !== undefined && purchase_price_inr !== null) {
    const val = Number(purchase_price_inr);
    if (!Number.isInteger(val) || val <= 0) {
      return res.status(422).json({
        error: 'Validation Error',
        detail: 'purchase_price_inr must be a positive integer.',
        status_code: 422,
      });
    }
  }

  // Validate times_worn
  if (times_worn !== undefined && times_worn !== null) {
    const val = Number(times_worn);
    if (!Number.isInteger(val) || val < 0) {
      return res.status(422).json({
        error: 'Validation Error',
        detail: 'times_worn must be a non-negative integer.',
        status_code: 422,
      });
    }
  }

  next();
}

/**
 * Validate params like userId and id
 */
function validateWardrobeParams(req, res, next) {
  const { id, userId } = req.params;

  if (id !== undefined && !UUID_REGEX.test(id)) {
    return res.status(422).json({
      error: 'Validation Error',
      detail: "Param 'id' must be a valid UUID.",
      status_code: 422,
    });
  }

  if (userId !== undefined && !UUID_REGEX.test(userId)) {
    return res.status(422).json({
      error: 'Validation Error',
      detail: "Param 'userId' must be a valid UUID.",
      status_code: 422,
    });
  }

  next();
}

module.exports = {
  validateWardrobeCreate,
  validateWardrobeParams,
};
