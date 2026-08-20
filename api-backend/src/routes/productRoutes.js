/**
 * Product Routes — api-backend.
 *
 * Endpoints:
 *   GET /products      — List products
 *   GET /products/:id  — Get product details by ID
 */

'use strict';

const express = require('express');
const router = express.Router();
const productController = require('../controllers/productController');

router.get('/', productController.listProducts);
router.get('/:id', productController.getProductById);

module.exports = router;
