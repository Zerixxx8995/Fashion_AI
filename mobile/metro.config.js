// Learn more https://docs.expo.dev/guides/customizing-metro
const { getDefaultConfig } = require('expo/metro-config');
const path = require('path');

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(__dirname);

// Use Metro's correct API for polyfills: polyfillModuleNames runs these
// files before anything else in the bundle — no recursion risk.
config.transformer = {
  ...config.transformer,
  polyfillModuleNames: [
    path.join(__dirname, 'polyfills.js'),
  ],
};

module.exports = config;
