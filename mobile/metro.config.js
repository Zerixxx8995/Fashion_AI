// Learn more https://docs.expo.dev/guides/customizing-metro
const { getDefaultConfig } = require('expo/metro-config');
const path = require('path');

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(__dirname);

// Redirect react-native's setUpPerformance to a minimal stub.
//
// The original setUpPerformance eagerly imports Performance.js → DOMException.js
// → PerformanceEntry.js → EventTiming.js → UserTiming.js … All of these files
// use private class fields (#name, #code, etc.) with Flow type annotations.
// Even with the correct Babel preset ordering in babel.config.js, the
// interaction between babel-preset-expo's @babel/preset-env and our additional
// class-properties plugins can cause the local class-name binding to drop,
// producing:
//   ReferenceError: Property 'DOMException' doesn't exist
//   ReferenceError: Property 'PerformanceEntry' doesn't exist
//   … and so on
//
// Redirecting setUpPerformance to a Date.now()-based stub bypasses this entire
// module tree in one step. The stub provides the performance.now() that React
// internals need (via nativePerformanceNow or Date.now), which is sufficient.
config.resolver = {
  ...config.resolver,
  resolveRequest: (context, moduleName, platform) => {
    if (
      context.originModulePath &&
      context.originModulePath.includes('react-native') &&
      (moduleName === '../../../Libraries/Core/setUpPerformance' ||
        moduleName.endsWith('/Core/setUpPerformance') ||
        moduleName.endsWith('\\Core\\setUpPerformance'))
    ) {
      return {
        filePath: path.resolve(__dirname, 'shims/setUpPerformance.js'),
        type: 'sourceFile',
      };
    }
    return context.resolveRequest(context, moduleName, platform);
  },
};

module.exports = config;
