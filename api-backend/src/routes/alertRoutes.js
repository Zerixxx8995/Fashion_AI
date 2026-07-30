/**
 * Alert Routes — api-backend.
 *
 * Responsibility: Map HTTP methods + URLs to alert controller functions.
 *
 * Architecture rules:
 *   Layer: Router
 *   One job: Route definitions only
 *   Never does: Business logic, DB access, response shaping
 *
 * Routes:
 *   POST   /alerts             — Create price drop or restock alert
 *   GET    /alerts/:userId     — Get all alerts for a user
 *   DELETE /alerts/:id         — Delete an alert
 */

'use strict';

const express = require('express');
const router = express.Router();

const authMiddleware = require('../middleware/authMiddleware');
const alertController = require('../controllers/alertController');
const { validateAlertCreate, validateAlertParams } = require('../validators/alertValidator');

// POST /alerts — create an alert (auth required)
router.post(
  '/',
  authMiddleware,
  validateAlertCreate,
  alertController.createAlert
);

// GET /alerts/:userId — get alerts for a user (auth required)
router.get(
  '/:userId',
  authMiddleware,
  validateAlertParams,
  alertController.getUserAlerts
);

// DELETE /alerts/:id — delete an alert (auth required)
router.delete(
  '/:id',
  authMiddleware,
  validateAlertParams,
  alertController.deleteAlert
);

module.exports = router;
