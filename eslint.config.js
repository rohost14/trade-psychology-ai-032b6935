import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    // Never lint build output, archived/dead code, the separate scroll-loss app,
    // the Python backend, or virtualenvs — these produced the bulk of the noise
    // that made `npm run lint` unusable as a gate.
    ignores: [
      "dist/**",
      "**/_archive/**",
      "scroll-loss-experience/**",
      "backend/**",
      "**/.venv/**",
      "**/venv/**",
      "**/node_modules/**",
    ],
  },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      "@typescript-eslint/no-unused-vars": "off",
      // Existing `any` debt (~90 uses) is visible as a warning rather than failing
      // the gate. New code should still avoid `any`; pay the debt down incrementally.
      "@typescript-eslint/no-explicit-any": "warn",
    },
  },
);
