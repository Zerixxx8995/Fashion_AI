/**
 * Wardrobe Controller — api-backend.
 *
 * Responsibility: Parse HTTP request, call wardrobeService, shape response.
 *
 * Architecture rules:
 *   Layer: Controller
 *   One job: Request parsing → service call → response shaping
 *   Never does: DB queries, business logic, gap analysis
 */

'use strict';

const wardrobeService = require('../services/wardrobeService');

const logger = {
  info:  (...args) => console.log('[wardrobe_controller]', ...args),
  error: (...args) => console.error('[wardrobe_controller]', ...args),
};

/**
 * POST /wardrobe
 * Add a new item to a user's wardrobe.
 */
async function addItem(req, res, next) {
  try {
    const {
      user_id, name, product_id, category, color,
      image_url, purchase_price_inr, times_worn,
    } = req.body;

    logger.info(`addItem user_id=${user_id}`);

    const item = await wardrobeService.addItem({
      user_id, name, product_id, category, color,
      image_url, purchase_price_inr, times_worn,
    });

    return res.status(201).json({ item });
  } catch (err) {
    next(err);
  }
}

/**
 * GET /wardrobe/:userId
 * Get all wardrobe items for a user.
 */
async function getItems(req, res, next) {
  try {
    const { userId } = req.params;
    logger.info(`getItems userId=${userId}`);

    const items = await wardrobeService.getItems(userId);
    return res.status(200).json({ items, count: items.length });
  } catch (err) {
    next(err);
  }
}

/**
 * DELETE /wardrobe/:id
 * Delete a wardrobe item.
 */
async function removeItem(req, res, next) {
  try {
    const { id } = req.params;
    logger.info(`removeItem id=${id}`);

    const deleted = await wardrobeService.removeItem(id);
    if (!deleted) {
      return res.status(404).json({
        error: 'Not Found',
        detail: `Wardrobe item with id '${id}' not found.`,
        status_code: 404,
      });
    }

    return res.status(200).json({ message: 'Wardrobe item removed.', id });
  } catch (err) {
    next(err);
  }
}

module.exports = { addItem, getItems, removeItem };
