/**
 * API Configuration
 *
 * Single source of truth for API-related configuration.
 * All API modules should import from here instead of accessing
 * import.meta.env.VITE_API_BASE_URL directly.
 */

/**
 * Base URL for the API server.
 * - Development: default to http(s)://<frontend-hostname>:8000 (supports LAN access)
 * - Production: default to same-origin (empty string), or set via VITE_API_BASE_URL
 */
const ENV_API_BASE_URL = import.meta.env.VITE_API_BASE_URL

const getDefaultDevApiBaseUrl = () => {
  // Vite supports SSR builds; keep a safe fallback when window is unavailable.
  if (import.meta.env.SSR || typeof window === 'undefined') {
    return 'http://localhost:8000'
  }

  const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:'
  const hostname = window.location.hostname || 'localhost'
  return `${protocol}//${hostname}:8000`
}

const DEFAULT_API_BASE_URL = import.meta.env.PROD ? '' : getDefaultDevApiBaseUrl()
const RAW_API_BASE_URL =
  typeof ENV_API_BASE_URL === 'string' ? ENV_API_BASE_URL : DEFAULT_API_BASE_URL

export function normalizeApiBaseUrl(rawValue: string): string {
  return rawValue.trim().replace(/\/+$/, '')
}

export function validateApiBaseUrl(rawValue: string): string {
  if (!rawValue) return ''

  if (!/^https?:\/\//i.test(rawValue)) {
    throw new Error(
      `Invalid VITE_API_BASE_URL: ${rawValue}. Expected an absolute http(s) URL, or leave empty for same-origin.`,
    )
  }

  const normalized = normalizeApiBaseUrl(rawValue)
  const pathname = new URL(normalized).pathname.replace(/\/+$/, '')

  if (pathname && pathname !== '/') {
    throw new Error(
      `Invalid VITE_API_BASE_URL: ${rawValue}. Use only the site origin (for example https://example.com), because API calls already include /api/v1 in their paths.`,
    )
  }

  return normalized
}

export const API_BASE_URL = validateApiBaseUrl(RAW_API_BASE_URL)

if (import.meta.env.DEV && /\/api(?:\/v1)?\/?$/i.test(normalizeApiBaseUrl(RAW_API_BASE_URL))) {
  console.warn(
    '[API] VITE_API_BASE_URL must not include /api or /api/v1. ' +
    'Most API calls in this app already include /api/v1 in their request paths.',
  )
}

/**
 * API v1 prefix
 */
export const API_V1_PREFIX = '/api/v1';

/**
 * Full API v1 base URL (convenience export)
 */
export const API_V1_URL = `${API_BASE_URL}${API_V1_PREFIX}`;

/**
 * Default request timeout in milliseconds
 */
export const API_TIMEOUT = 30000;

/**
 * Admin API Key for authenticated admin endpoints.
 * Required when backend has ADMIN_REQUIRE_API_KEY=true (production default)
 * Set via VITE_ADMIN_API_KEY environment variable
 *
 * ⚠️ SECURITY WARNING ⚠️
 * This key is embedded in the frontend build (DEV only). Only use when:
 * - Admin page is restricted to internal network/VPN, OR
 * - Reverse proxy injects X-Admin-API-Key header instead
 * For public deployments, use backend session-based auth.
 *
 * @see docs/SECURITY_DEPLOYMENT.md for secure deployment patterns
 */
// SECURITY: Never allow embedding Admin API Key into production bundles.
// - In production builds, always force the exported key to empty string.
// - In dev builds, allow using VITE_ADMIN_API_KEY for local testing only.
//
// Rationale:
// Any VITE_* value is statically embedded into the JS bundle by Vite.
// If a key is present during a production build, it can be extracted from dist/.
export const ADMIN_API_KEY = import.meta.env.DEV
  ? (import.meta.env.VITE_ADMIN_API_KEY || '')
  : '';

// Runtime warning for developers (DEV only).
// Note: Production builds must fail-fast at build time (see vite.config.ts / CI guardrails).
if (import.meta.env.DEV && ADMIN_API_KEY) {
  console.warn(
    '%c⚠️ SECURITY WARNING: VITE_ADMIN_API_KEY is set (DEV build).\n' +
    'This key will be embedded into the frontend bundle.\n' +
    'Do NOT use this for public deployments; prefer reverse proxy injection or backend auth.\n' +
    'See: docs/SECURITY_DEPLOYMENT.md',
    'color: red; font-weight: bold; font-size: 14px;'
  );
}
