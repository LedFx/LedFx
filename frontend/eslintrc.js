module.exports = {
    root: true,
    parser: '@typescript-eslint/parser',
    parserOptions: {
        ecmaVersion: 2018,
        ecmaFeatures: {
            legacyDecorators: true,
        },
        sourceType: 'module',
    },
    extends: ['plugin:@typescript-eslint/eslint-recommended', 'prettier', 'prettier/react'],
    plugins: [
        'react',
        '@typescript-eslint',
        'prettier',
    ],
    globals: {
        __DEV__: false,
        jest: false,
        jasmine: false,
        it: false,
        describe: false,
        expect: false,
        element: false,
        by: false,
        beforeAll: false,
        beforeEach: false,
        afterAll: false,
    },
    rules: {
        'prettier/prettier': 'error',
        'no-shadow': 'off',
    },
};
