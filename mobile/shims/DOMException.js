/**
 * shims/DOMException.js
 *
 * Safe replacement for react-native's DOMException.js
 * (node_modules/react-native/src/private/webapis/errors/DOMException.js).
 *
 * The original file uses private class fields (#name, #code) together with
 * Flow type annotations, and calls setPlatformObject(DOMException, {...})
 * AFTER the class body.  The combination of Babel's Flow-strip and
 * class-properties transforms can drop the local `DOMException` binding so
 * those post-class lines throw:
 *   ReferenceError: Property 'DOMException' doesn't exist
 *
 * This file avoids ALL of those issues:
 *  • No private fields          → no transform interaction bugs
 *  • Uses `const` binding       → local name is always preserved
 *  • Sets global.DOMException   → fixes the whatwg-fetch try-catch too
 *  • Exports the same API       → drop-in replacement for callers
 */

var ERROR_NAME_TO_ERROR_CODE_MAP = {
  IndexSizeError: 1,
  HierarchyRequestError: 3,
  WrongDocumentError: 4,
  InvalidCharacterError: 5,
  NoModificationAllowedError: 7,
  NotFoundError: 8,
  NotSupportedError: 9,
  InUseAttributeError: 10,
  InvalidStateError: 11,
  SyntaxError: 12,
  InvalidModificationError: 13,
  NamespaceError: 14,
  InvalidAccessError: 15,
  TypeMismatchError: 17,
  SecurityError: 18,
  NetworkError: 19,
  AbortError: 20,
  URLMismatchError: 21,
  QuotaExceededError: 22,
  TimeoutError: 23,
  InvalidNodeTypeError: 24,
  DataCloneError: 25,
};

var ERROR_CODES = {
  INDEX_SIZE_ERR: 1,
  DOMSTRING_SIZE_ERR: 2,
  HIERARCHY_REQUEST_ERR: 3,
  WRONG_DOCUMENT_ERR: 4,
  INVALID_CHARACTER_ERR: 5,
  NO_DATA_ALLOWED_ERR: 6,
  NO_MODIFICATION_ALLOWED_ERR: 7,
  NOT_FOUND_ERR: 8,
  NOT_SUPPORTED_ERR: 9,
  INUSE_ATTRIBUTE_ERR: 10,
  INVALID_STATE_ERR: 11,
  SYNTAX_ERR: 12,
  INVALID_MODIFICATION_ERR: 13,
  NAMESPACE_ERR: 14,
  INVALID_ACCESS_ERR: 15,
  VALIDATION_ERR: 16,
  TYPE_MISMATCH_ERR: 17,
  SECURITY_ERR: 18,
  NETWORK_ERR: 19,
  ABORT_ERR: 20,
  URL_MISMATCH_ERR: 21,
  QUOTA_EXCEEDED_ERR: 22,
  TIMEOUT_ERR: 23,
  INVALID_NODE_TYPE_ERR: 24,
  DATA_CLONE_ERR: 25,
};

// ── Constructor (no private fields — avoids Babel transform interaction bugs) ──
function DOMException(message, name) {
  // Allow calling as a constructor or regular function
  Error.call(this, message);
  this.message = message != null ? String(message) : '';
  var resolvedName = (typeof name === 'undefined') ? 'Error' : String(name);
  // Store on underscore-prefixed properties to avoid conflict with the getters
  this._domExceptionName = resolvedName;
  this._domExceptionCode = ERROR_NAME_TO_ERROR_CODE_MAP[resolvedName] || 0;
}

DOMException.prototype = Object.create(Error.prototype);
DOMException.prototype.constructor = DOMException;

Object.defineProperty(DOMException.prototype, 'name', {
  get: function() { return this._domExceptionName; },
  enumerable: true,
  configurable: true,
});

Object.defineProperty(DOMException.prototype, 'code', {
  get: function() { return this._domExceptionCode; },
  enumerable: true,
  configurable: true,
});

// Add numeric code constants to both the constructor and prototype
for (var _code in ERROR_CODES) {
  if (Object.prototype.hasOwnProperty.call(ERROR_CODES, _code)) {
    Object.defineProperty(DOMException, _code, {
      enumerable: true,
      configurable: true,
      writable: false,
      value: ERROR_CODES[_code],
    });
    Object.defineProperty(DOMException.prototype, _code, {
      enumerable: true,
      configurable: true,
      writable: false,
      value: ERROR_CODES[_code],
    });
  }
}

// ── Also expose as a global so whatwg-fetch's `g.DOMException` check works ──
if (typeof global !== 'undefined' && !global.DOMException) {
  global.DOMException = DOMException;
}
if (typeof globalThis !== 'undefined' && !globalThis.DOMException) {
  globalThis.DOMException = DOMException;
}

export default DOMException;
