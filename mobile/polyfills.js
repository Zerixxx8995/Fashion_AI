/**
 * Global Polyfills — mobile/polyfills.js
 *
 * Responsibility: Register global runtime polyfills before any React Native
 * or library code executes.
 */

// Polyfill global.DOMException for Hermes compatibility
if (typeof global.DOMException === 'undefined') {
  global.DOMException = class DOMException extends Error {
    constructor(message, name) {
      super(message);
      this.name = name || 'DOMException';
    }
  };
}
