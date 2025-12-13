import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  // ==========================================
  // Base configuration for all TypeScript files
  // ==========================================
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // TypeScript rules
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],

      // React Hooks rules
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      // Disable set-state-in-effect check - calling setState synchronously in useEffect
      // is a normal React pattern for syncing props to state or updating state based on side effects
      'react-hooks/set-state-in-effect': 'off',

      // General rules - strict for src/
      'no-console': ['warn', { allow: ['warn', 'error'] }],
      'prefer-const': 'warn',
      'no-debugger': 'error',
    },
  },
  // ==========================================
  // Relaxed rules for test files (e2e/, tests/, __tests__/)
  // ==========================================
  {
    files: [
      'e2e/**/*.{ts,tsx}',
      'tests/**/*.{ts,tsx}',
      '**/__tests__/**/*.{ts,tsx}',
      '**/*.test.{ts,tsx}',
      '**/*.spec.{ts,tsx}',
      'src/test/**/*.{ts,tsx}',
    ],
    rules: {
      // Allow console in tests for debugging
      'no-console': 'off',
      // Allow any in tests for mocking flexibility
      '@typescript-eslint/no-explicit-any': 'off',
      // Allow unused vars in tests (common for destructuring)
      '@typescript-eslint/no-unused-vars': 'off',
    },
  },
])
