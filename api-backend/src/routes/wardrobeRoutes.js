/**
 * Wardrobe Routes — api-backend.
 *
 * Responsibility: Map HTTP methods + URLs to wardrobe controller functions.
 *
 * Architecture rules:
 *   Layer: Router
 *   One job: Route definitions only
 *   Never does: Business logic, DB access, response shaping
 *
 * Routes:
 *   POST   /wardrobe              — Add item to wardrobe
 *   GET    /wardrobe/:userId      — Get all items for a user
 *   DELETE /wardrobe/:id          — Remove an item
 */

'use strict';

const express = require('express');
const router = express.Router();

const authMiddleware = require('../middleware/authMiddleware');
const wardrobeController = require('../controllers/wardrobeController');
const { validateWardrobeCreate, validateWardrobeParams } = require('../validators/wardrobeValidator');

// POST /wardrobe — add item (auth required)
router.post(
  '/',
  authMiddleware,
  validateWardrobeCreate,
  wardrobeController.addItem
);

// GET /wardrobe/:userId — get all items for a user (auth required)
router.get(
  '/:userId',
  authMiddleware,
  validateWardrobeParams,
  wardrobeController.getItems
);

// DELETE /wardrobe/:id — remove an item (auth required)
router.delete(
  '/:id',
  authMiddleware,
  validateWardrobeParams,
  wardrobeController.removeItem
);

module.exports = router;
