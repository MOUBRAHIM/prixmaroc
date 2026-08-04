module.exports = function (api) {
  api.cache(true);
  return {
    presets: [
      ['babel-preset-expo', { jsxImportSource: 'nativewind' }],
    ],
    plugins: [
      [
        'module-resolver',
        {
          root: ['./src'],
          alias: {
            '@': './src',
            '@nav': './src/navigation',
            '@screens': './src/screens',
            '@components': './src/components',
            '@services': './src/services',
            '@store': './src/store',
            '@hooks': './src/hooks',
            '@types': './src/types',
            '@constants': './src/constants',
            '@utils': './src/utils',
          },
        },
      ],
      'react-native-reanimated/plugin',
    ],
  };
};
