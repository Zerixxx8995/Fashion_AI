/**
 * Wardrobe Service — api-backend.
 *
 * Responsibility: All business logic for wardrobe item CRUD.
 *
 * Architecture rules:
 *   Layer: Service
 *   One job: Wardrobe item read/write operations
 *   Never does: HTTP routing, response shaping, gap analysis algorithm (that's ml-backend)
 *
 * Operations:
 *   addItem      — Persist a new wardrobe item for a user
 *   getItems     — Fetch all wardrobe items for a user
 *   removeItem   — Hard-delete a wardrobe item by id
 */

'use strict';

const WardrobeItem = require('../models/WardrobeItem');

const logger = {
  info:  (...args) => console.log('[wardrobe_service]', ...args),
  warn:  (...args) => console.warn('[wardrobe_service]', ...args),
  error: (...args) => console.error('[wardrobe_service]', ...args),
};

/**
 * Add a new item to a user's wardrobe.
 *
 * @param {object} data
 * @param {string} data.user_id
 * @param {string} data.name
 * @param {string|null} [data.product_id]
 * @param {string|null} [data.category]
 * @param {string|null} [data.color]
 * @param {string|null} [data.image_url]
 * @param {number|null} [data.purchase_price_inr]
 * @param {number}      [data.times_worn=0]
 * @returns {Promise<WardrobeItem>}
 */
async function addItem({
  user_id,
  name,
  product_id = null,
  category = null,
  color = null,
  image_url = null,
  purchase_price_inr = null,
  times_worn = 0,
}) {
  logger.info(`addItem user_id=${user_id} name="${name}"`);

  const item = await WardrobeItem.create({
    user_id,
    product_id,
    name: name.trim(),
    category: category ? category.trim() : null,
    color: color ? color.trim() : null,
    image_url: image_url || null,
    purchase_price_inr: purchase_price_inr || null,
    times_worn: times_worn ?? 0,
  });

  logger.info(`created wardrobe item id=${item.id}`);
  return item;
}

/**
 * Get all wardrobe items for a user.
 *
 * @param {string} userId
 * @returns {Promise<WardrobeItem[]>}
 */
async function getItems(userId) {
  logger.info(`getItems userId=${userId}`);
  return WardrobeItem.findAll({
    where: { user_id: userId },
    order: [['added_at', 'DESC']],
  });
}

/**
 * Delete a wardrobe item by id.
 * Returns null if not found.
 *
 * @param {string} itemId
 * @returns {Promise<WardrobeItem|null>}
 */
async function removeItem(itemId) {
  logger.info(`removeItem id=${itemId}`);
  const item = await WardrobeItem.findByPk(itemId);
  if (!item) {
    logger.warn(`removeItem: item not found id=${itemId}`);
    return null;
  }
  await item.destroy();
  logger.info(`deleted wardrobe item id=${itemId}`);
  return item;
}

module.exports = { addItem, getItems, removeItem };
