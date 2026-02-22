/**
 * Auth helper — centralized access token retrieval from Keycloak.
 * 
 * All components should use `getAccessToken()` for getting Bearer tokens.
 */
import keycloak from './keycloakClient';

/**
 * Get the current access token from Keycloak.
 * Auto-refreshes if the token is expired or about to expire.
 * 
 * @returns The access token string
 * @throws Error if not authenticated or token refresh fails
 */
export async function getAccessToken(): Promise<string> {
    if (!keycloak.authenticated || !keycloak.token) {
        throw new Error('Not authenticated. Please login.');
    }

    // Refresh token if it expires within 30 seconds
    try {
        const refreshed = await keycloak.updateToken(30);
        if (refreshed) {
            console.debug('Token was refreshed');
        }
    } catch {
        throw new Error('Session expired. Please login again.');
    }

    return keycloak.token;
}
