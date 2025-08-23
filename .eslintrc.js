module.exports = {
  env: {
    browser: true,
    es2021: true,
    node: true
  },
  extends: [
    'standard'
  ],
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    requireConfigFile: false,
    babelOptions: {
      configFile: './babel.config.js'
    }
  },
  parser: '@babel/eslint-parser',
  plugins: [
    'import'
  ],
  rules: {
    'indent': ['error', 2],
    'linebreak-style': ['error', 'unix'],
    'quotes': ['error', 'single'],
    'semi': ['error', 'always'],
    'no-unused-vars': 'warn',
    'no-console': 'warn'
  },
  overrides: [
    {
      files: ['static/js/**/*.js'],
      parserOptions: {
        requireConfigFile: false
      }
    }
  ]
};
