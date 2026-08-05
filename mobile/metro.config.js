// Learn more https://docs.expo.dev/guides/customizing-metro
const { getDefaultConfig } = require('expo/metro-config');
const path = require('path');

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(__dirname);

// Inject polyfills.js so it executes before any other module in the bundle
config.serializer = {
  ...config.serializer,
  getModulesRunBeforeMainModule: (entryPoint) => [
    path.join(__dirname, 'polyfills.js'),
    ...(config.serializer.getModulesRunBeforeMainModule
      ? config.serializer.getModulesRunBeforeMainModule(entryPoint)
      : []),
  ],
};

module.exports = config;
