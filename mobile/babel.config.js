module.exports = function (api) {
  api.cache(true);
  return {
    presets: [
      // babel-preset-expo handles everything:
      //  - Flow/TS type stripping (via `overrides`, which run before sub-preset plugins)
      //  - Class properties, private methods, private-property-in-object (hermes-v0 config)
      //  - JSX, async/await, Expo Router, Reanimated, etc.
      //
      // The hermes-v0 config already includes:
      //   @babel/plugin-transform-class-properties
      //   @babel/plugin-transform-private-methods
      //   @babel/plugin-transform-private-property-in-object
      // — all with loose: true, and applied AFTER Flow stripping.
      //
      // Adding our own copies of those plugins (double-applying) caused them to run
      // on partially-processed AST, breaking class bindings and producing:
      //   ReferenceError: Property 'MessageQueue' doesn't exist
      'babel-preset-expo',
    ],
  };
};
