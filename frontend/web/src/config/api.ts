/**
 * API Configuration
 *
 * Single source of truth for API-related configuration.
 * All API modules should import from here instead of accessing
 * import.meta.env.VITE_API_BASE_URL directly.
 */

/**
 * Base URL for the API server.
 * - Development: http://localhost:8000 (default)
 * - Production: Set via VITE_API_BASE_URL environment variable
 */
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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
