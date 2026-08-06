/* eslint-env node */
// ESLint-конфигурация Vektor (AGENTS.md §7.2).
// ESLint 8 (.eslintrc) — стабилен и совместим с @typescript-eslint v8.
module.exports = {
  root: true,
  env: { browser: true, es2022: true, node: true },
  ignorePatterns: ["dist", "node_modules", "coverage", "*.config.ts", "*.cjs", "eslint.config.*"],
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module",
    ecmaFeatures: { jsx: true },
  },
  settings: {
    react: { version: "detect" },
  },
  plugins: ["@typescript-eslint", "react", "react-hooks", "react-refresh"],
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react/recommended",
    "plugin:react/jsx-runtime", // React 18 — новый JSX-runtime без React in scope
    "plugin:react-hooks/recommended",
    "prettier", // отключает правила, конфликтующие с Prettier
  ],
  rules: {
    "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
    "@typescript-eslint/consistent-type-imports": [
      "error",
      { prefer: "type-imports", fixStyle: "inline-type-imports" },
    ],
    "@typescript-eslint/no-unused-vars": [
      "error",
      { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
    ],
    "react/prop-types": "off", // TypeScript покрывает проверки пропсов
    "no-console": ["warn", { allow: ["warn", "error"] }],
  },
};
