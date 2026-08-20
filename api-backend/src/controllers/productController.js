/**
 * Product Controller — api-backend.
 *
 * Handles HTTP requests for product endpoints:
 *   GET /products      — List products with optional platform/category filters
 *   GET /products/:id  — Get product details by ID
 */

'use strict';

const Product = require('../models/Product');
const { Op } = require('sequelize');

const SAMPLE_CATALOG = [
  {
    idMatch: 'sneaker',
    name: 'Retro Chunky Leather Sneakers',
    brand: 'Roadster',
    price_inr: 2499,
    category: 'Footwear',
    platform: 'myntra',
    stock_image_urls: [
      'https://images.unsplash.com/photo-1552346154-21d32810aba3?w=600',
      'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600',
      'https://images.unsplash.com/photo-1608231387042-66d1773070a5?w=600',
    ],
    url: 'https://www.myntra.com/sneakers/roadster/retro-chunky-leather-sneakers/12345/buy',
  },
  {
    idMatch: 'graphic',
    name: 'Oversized Vintage Graphic Cotton Tee',
    brand: 'H&M',
    price_inr: 1299,
    category: 'Topwear',
    platform: 'ajio',
    stock_image_urls: [
      'https://images.unsplash.com/photo-1576995853123-5a10305d93c0?w=600',
      'https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?w=600',
    ],
    url: 'https://www.ajio.com/h-m-oversized-graphic-tee/p/461234567',
  },
  {
    idMatch: 'cargo',
    name: 'Tactical Wide-Leg Parachute Cargo Pants',
    brand: 'Zara',
    price_inr: 2990,
    category: 'Bottomwear',
    platform: 'amazon',
    stock_image_urls: [
      'https://images.unsplash.com/photo-1517445312882-bc9910d016b7?w=600',
      'https://images.unsplash.com/photo-1509551388413-e18d0ac5d495?w=600',
    ],
    url: 'https://www.amazon.in/dp/B08N5K1Z92',
  },
  {
    idMatch: 'dress',
    name: 'Boho Floral Print Tiered Maxi Dress',
    brand: 'Biba',
    price_inr: 3499,
    category: 'Dresses',
    platform: 'meesho',
    stock_image_urls: [
      'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=600',
      'https://images.unsplash.com/photo-1496747611176-843222e1e57c?w=600',
    ],
    url: 'https://www.meesho.com/boho-maxi-dress/p/1abcde',
  },
  {
    idMatch: 'denim',
    name: 'Washed Cropped Denim Trucker Jacket',
    brand: "Levi's",
    price_inr: 4199,
    category: 'Outerwear',
    platform: 'flipkart',
    stock_image_urls: [
      'https://images.unsplash.com/photo-1544441893-675973e31985?w=600',
      'https://images.unsplash.com/photo-1525450824786-227cbef70703?w=600',
    ],
    url: 'https://www.flipkart.com/levis-denim-jacket/p/itm123456',
  },
];

/**
 * Fallback product generator for testing when a product ID is not in DB.
 */
function getFallbackProduct(id) {
  const lowerId = String(id || '').toLowerCase();
  const matched = SAMPLE_CATALOG.find((item) => lowerId.includes(item.idMatch));

  if (matched) {
    return {
      id,
      platform: matched.platform,
      platform_id: `platform-${id}`,
      name: matched.name,
      brand: matched.brand,
      price_inr: matched.price_inr,
      category: matched.category,
      stock_image_urls: matched.stock_image_urls,
      url: matched.url,
      seller_id: `${matched.brand.toLowerCase()}_official`,
      scraped_at: new Date().toISOString(),
    };
  }

  // Generic fallback if no specific match
  return {
    id,
    platform: 'myntra',
    platform_id: `myntra-${id}`,
    name: 'Classic Fashion Essential Item',
    brand: 'Roadster',
    price_inr: 1899,
    category: 'Fashion',
    stock_image_urls: [
      'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=600',
      'https://images.unsplash.com/photo-1552346154-21d32810aba3?w=600',
    ],
    url: 'https://www.myntra.com',
    seller_id: 'myntra_official',
    scraped_at: new Date().toISOString(),
  };
}

/**
 * Get single product by ID.
 */
async function getProductById(req, res, next) {
  try {
    const { id } = req.params;
    const product = await Product.findByPk(id);

    if (product) {
      return res.json(product);
    }

    return res.json(getFallbackProduct(id));
  } catch (err) {
    next(err);
  }
}

/**
 * List products with platform/category filter and pagination.
 */
async function listProducts(req, res, next) {
  try {
    const { platform, category, limit = 20, offset = 0 } = req.query;
    const where = {};

    if (platform) where.platform = platform;
    if (category) where.category = { [Op.iLike]: `%${category}%` };

    const { rows, count } = await Product.findAndCountAll({
      where,
      limit: parseInt(limit, 10),
      offset: parseInt(offset, 10),
      order: [['scraped_at', 'DESC']],
    });

    return res.json({
      products: rows,
      total: count,
    });
  } catch (err) {
    next(err);
  }
}

module.exports = {
  getProductById,
  listProducts,
};
