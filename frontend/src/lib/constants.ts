/**
 * Shared application constants.
 * Import from here instead of re-declaring in multiple files.
 */

/**
 * Custom DOM event name emitted when the API receives a 401 Unauthorized.
 * AuthProvider listens for this and clears in-memory auth state.
 */
export const AUTH_LOGOUT_EVENT = "dbmanager:logout"
