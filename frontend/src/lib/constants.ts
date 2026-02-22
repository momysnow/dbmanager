/**
 * Shared application constants.
 * Import from here instead of re-declaring in multiple files.
 */

/** localStorage key used to persist the JWT access token */
export const TOKEN_KEY = "dbmanager_token"

/** Custom DOM event name emitted when the API receives a 401 Unauthorized */
export const AUTH_LOGOUT_EVENT = "dbmanager:logout"
