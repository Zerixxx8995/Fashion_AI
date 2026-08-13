/**
 * shims/setUpPerformance.js
 *
 * Minimal drop-in replacement for react-native's setUpPerformance.js.
 *
 * The original file imports a large tree of performance modules
 * (Performance.js → PerformanceEntry.js → EventTiming.js → UserTiming.js …)
 * all of which use private class fields (#name, #code, etc.) with Flow type
 * annotations.  The Babel Flow-strip + class-properties transform combination
 * drops local class-name bindings, causing cascading:
 *   ReferenceError: Property '<ClassName>' doesn't exist
 *
 * This stub provides a working global.performance object (using Date.now for
 * timing) without importing any of those problematic modules.  The full W3C
 * Performance API is not needed for this React Native app.
 */

if (!global.performance) {
  global.performance = {
    // Core timing (used by React profiling, animations, etc.)
    now: function() {
      var nativeNow = global.nativePerformanceNow;
      return nativeNow ? nativeNow() : Date.now();
    },
    // Stub methods (User Timing API – not needed for auth/UI)
    mark: function() {},
    measure: function() {},
    clearMarks: function() {},
    clearMeasures: function() {},
    getEntries: function() { return []; },
    getEntriesByType: function() { return []; },
    getEntriesByName: function() { return []; },
    setResourceTimingBufferSize: function() {},
    clearResourceTimings: function() {},
    toJSON: function() { return {}; },
    eventCounts: { size: 0 },
  };
}
