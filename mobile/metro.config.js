// Learn more https://docs.expo.dev/guides/customizing-metro
const { getDefaultConfig } = require('expo/metro-config');

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(__dirname);

config.serializer = {
  ...config.serializer,
  getModulesRunBeforeMainModule: (entryPoint) => [
    path.join(__dirname, 'polyfills.js'),
    require.resolve('react-native/Libraries/Core/InitializeCore.js'),
    require.resolve('expo/src/winter/index.ts'),
    require.resolve('@expo/metro-runtime/src/index.ts'),
  ],
};

module.exports = config;
