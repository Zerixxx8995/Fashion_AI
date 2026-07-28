/**
 * Tests for api-backend validators.
 *
 * Asserts:
 *   - Valid input passes through and calls next().
 *   - Invalid inputs return 422 with a structured error JSON.
 */

'use strict';

const { validateUserSync, validateUserProfileUpdate } = require('../src/validators/userValidator');
const { validateAlertCreate, validateAlertParams } = require('../src/validators/alertValidator');
const { validateWardrobeCreate, validateWardrobeParams } = require('../src/validators/wardrobeValidator');

function mockRes() {
  const res = {};
  res.status = jest.fn().mockReturnValue(res);
  res.json = jest.fn().mockReturnValue(res);
  return res;
}

function mockNext() {
  return jest.fn();
}

describe('User Validator Middleware', () => {
  // POST /auth/sync tests
  describe('validateUserSync', () => {
    test('passes valid input', () => {
      const req = {
        body: {
          clerk_id: 'user_2bd1bcc8',
          email: 'test@example.com',
          name: 'John Doe',
        },
      };
      const res = mockRes();
      const next = mockNext();

      validateUserSync(req, res, next);
      expect(next).toHaveBeenCalled();
      expect(res.status).not.toHaveBeenCalled();
    });

    test('rejects empty clerk_id', () => {
      const req = {
        body: {
          clerk_id: '',
          email: 'test@example.com',
        },
      };
      const res = mockRes();
      const next = mockNext();

      validateUserSync(req, res, next);
      expect(res.status).toHaveBeenCalledWith(422);
      expect(res.json).toHaveBeenCalledWith(expect.objectContaining({
        error: 'Validation Error',
        detail: expect.stringContaining('clerk_id'),
      }));
      expect(next).not.toHaveBeenCalled();
    });

    test('rejects invalid email', () => {
      const req = {
        body: {
          clerk_id: 'user_2bd1bcc8',
          email: 'bad-email-format',
        },
      };
      const res = mockRes();
      const next = mockNext();

      validateUserSync(req, res, next);
      expect(res.status).toHaveBeenCalledWith(422);
      expect(res.json).toHaveBeenCalledWith(expect.objectContaining({
        error: 'Validation Error',
        detail: expect.stringContaining('email'),
      }));
      expect(next).not.toHaveBeenCalled();
    });
  });

  // PUT /users/:id/profile tests
  describe('validateUserProfileUpdate', () => {
    test('passes valid inputs', () => {
      const req = {
        params: { id: 'c8b4df56-e918-4b72-8f52-64f33b1e3271' },
        body: {
          body_type: 'rectangle',
          height_cm: 180,
          weight_kg: 75,
          measurements: { chest: 96.5, waist: 82.0 },
          style_preferences: ['casual', 'smart'],
          skin_tone: 'medium',
        },
      };
      const res = mockRes();
      const next = mockNext();

      validateUserProfileUpdate(req, res, next);
      expect(next).toHaveBeenCalled();
    });

    test('rejects invalid UUID param', () => {
      const req = {
        params: { id: 'bad-uuid-123' },
        body: {},
      };
      const res = mockRes();
      const next = mockNext();

      validateUserProfileUpdate(req, res, next);
      expect(res.status).toHaveBeenCalledWith(422);
      expect(res.json).toHaveBeenCalledWith(expect.objectContaining({
        detail: expect.stringContaining('must be a valid UUID'),
      }));
    });

    test('rejects negative height', () => {
      const req = {
        params: { id: 'c8b4df56-e918-4b72-8f52-64f33b1e3271' },
        body: { height_cm: -10 },
      };
      const res = mockRes();
      const next = mockNext();

      validateUserProfileUpdate(req, res, next);
      expect(res.status).toHaveBeenCalledWith(422);
      expect(res.json).toHaveBeenCalledWith(expect.objectContaining({
        detail: expect.stringContaining('height_cm'),
      }));
    });

    test('rejects bad measurements shape', () => {
      const req = {
        params: { id: 'c8b4df56-e918-4b72-8f52-64f33b1e3271' },
        body: { measurements: ['chest', 95] }, // array instead of object
      };
      const res = mockRes();
      const next = mockNext();

      validateUserProfileUpdate(req, res, next);
      expect(res.status).toHaveBeenCalledWith(422);
      expect(res.json).toHaveBeenCalledWith(expect.objectContaining({
        detail: expect.stringContaining('measurements'),
      }));
    });
  });
});

describe('Alert Validator Middleware', () => {
  describe('validateAlertCreate', () => {
    test('passes valid price_drop alert', () => {
      const req = {
        body: {
          user_id: 'c8b4df56-e918-4b72-8f52-64f33b1e3271',
          product_id: 'a8b4df56-e918-4b72-8f52-64f33b1e3271',
          alert_type: 'price_drop',
          target_price_inr: 599,
        },
      };
      const res = mockRes();
      const next = mockNext();

      validateAlertCreate(req, res, next);
      expect(next).toHaveBeenCalled();
    });

    test('passes valid restock alert', () => {
      const req = {
        body: {
          user_id: 'c8b4df56-e918-4b72-8f52-64f33b1e3271',
          product_id: 'a8b4df56-e918-4b72-8f52-64f33b1e3271',
          alert_type: 'restock',
        },
      };
      const res = mockRes();
      const next = mockNext();

      validateAlertCreate(req, res, next);
      expect(next).toHaveBeenCalled();
    });

    test('rejects price_drop alert without target_price_inr', () => {
      const req = {
        body: {
          user_id: 'c8b4df56-e918-4b72-8f52-64f33b1e3271',
          product_id: 'a8b4df56-e918-4b72-8f52-64f33b1e3271',
          alert_type: 'price_drop',
        },
      };
      const res = mockRes();
      const next = mockNext();

      validateAlertCreate(req, res, next);
      expect(res.status).toHaveBeenCalledWith(422);
      expect(res.json).toHaveBeenCalledWith(expect.objectContaining({
        detail: expect.stringContaining('target_price_inr is required'),
      }));
    });

    test('rejects restock alert with target_price_inr', () => {
      const req = {
        body: {
          user_id: 'c8b4df56-e918-4b72-8f52-64f33b1e3271',
          product_id: 'a8b4df56-e918-4b72-8f52-64f33b1e3271',
          alert_type: 'restock',
          target_price_inr: 500,
        },
      };
      const res = mockRes();
      const next = mockNext();

      validateAlertCreate(req, res, next);
      expect(res.status).toHaveBeenCalledWith(422);
      expect(res.json).toHaveBeenCalledWith(expect.objectContaining({
        detail: expect.stringContaining('must not be set for \'restock\''),
      }));
    });
  });

  describe('validateAlertParams', () => {
    test('passes valid UUID params', () => {
      const req = {
        params: {
          id: 'c8b4df56-e918-4b72-8f52-64f33b1e3271',
          userId: 'a8b4df56-e918-4b72-8f52-64f33b1e3271',
        },
      };
      const res = mockRes();
      const next = mockNext();

      validateAlertParams(req, res, next);
      expect(next).toHaveBeenCalled();
    });

    test('rejects invalid userId param', () => {
      const req = {
        params: {
          userId: 'bad-uuid',
        },
      };
      const res = mockRes();
      const next = mockNext();

      validateAlertParams(req, res, next);
      expect(res.status).toHaveBeenCalledWith(422);
    });
  });
});

describe('Wardrobe Validator Middleware', () => {
  describe('validateWardrobeCreate', () => {
    test('passes valid inputs', () => {
      const req = {
        body: {
          user_id: 'c8b4df56-e918-4b72-8f52-64f33b1e3271',
          product_id: 'a8b4df56-e918-4b72-8f52-64f33b1e3271',
          name: 'My Nike Sneakers',
          category: 'footwear',
          color: 'black',
          image_url: 'https://images.com/nike.png',
          purchase_price_inr: 4999,
          times_worn: 2,
        },
      };
      const res = mockRes();
      const next = mockNext();

      validateWardrobeCreate(req, res, next);
      expect(next).toHaveBeenCalled();
    });

    test('rejects missing name', () => {
      const req = {
        body: {
          user_id: 'c8b4df56-e918-4b72-8f52-64f33b1e3271',
          category: 'footwear',
        },
      };
      const res = mockRes();
      const next = mockNext();

      validateWardrobeCreate(req, res, next);
      expect(res.status).toHaveBeenCalledWith(422);
      expect(res.json).toHaveBeenCalledWith(expect.objectContaining({
        detail: expect.stringContaining('name'),
      }));
    });

    test('rejects negative times_worn', () => {
      const req = {
        body: {
          user_id: 'c8b4df56-e918-4b72-8f52-64f33b1e3271',
          name: 'Shirt',
          times_worn: -5,
        },
      };
      const res = mockRes();
      const next = mockNext();

      validateWardrobeCreate(req, res, next);
      expect(res.status).toHaveBeenCalledWith(422);
    });
  });

  describe('validateWardrobeParams', () => {
    test('passes valid UUID id', () => {
      const req = {
        params: { id: 'c8b4df56-e918-4b72-8f52-64f33b1e3271' },
      };
      const res = mockRes();
      const next = mockNext();

      validateWardrobeParams(req, res, next);
      expect(next).toHaveBeenCalled();
    });

    test('rejects invalid id param', () => {
      const req = {
        params: { id: 'bad-uuid' },
      };
      const res = mockRes();
      const next = mockNext();

      validateWardrobeParams(req, res, next);
      expect(res.status).toHaveBeenCalledWith(422);
    });
  });
});
