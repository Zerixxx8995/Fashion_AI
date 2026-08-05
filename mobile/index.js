/**
 * Custom Entry Point — mobile/index.js
 *
 * Responsibility: Run early global runtime polyfills before booting Expo Router.
 * This is the true root entry of the JavaScript bundle.
 */

// Hermes React Native polyfill for global DOMException
// Must be defined at the absolute beginning before any libraries are loaded.
if (typeof global.DOMException === 'undefined') {
  global.DOMException = class DOMException extends Error {
    constructor(message, name) {
      super(message);
      this.name = name || 'DOMException';
    }
  };
}

// Boot Expo Router
import 'expo-router/entry';
