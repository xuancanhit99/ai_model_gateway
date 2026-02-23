import Keycloak from 'keycloak-js';
import { getStorageScope, resolveCurrentAuthuser } from './keycloakMultiAccount';

/**
 * IDSafe (Keycloak) OIDC client for authentication.
 * Replaces Supabase Auth for user login/logout.
 */
export const IDSAFE_BASE_AUTH_URL = (import.meta.env.VITE_IDSAFE_URL || 'https://sso.vnpay.dev').replace(/\/+$/, '');
export const IDSAFE_REALM = import.meta.env.VITE_IDSAFE_REALM || 'idsafe-uat';
export const IDSAFE_CLIENT_ID = import.meta.env.VITE_IDSAFE_CLIENT_ID || 'hyper-ai-gateway';

const normalizeAuthServerUrl = (candidate: string): string => candidate.replace(/\/+$/, '');

const resolveStoredAuthuser = (): string | null => {
    try {
        const scope = getStorageScope(IDSAFE_REALM, IDSAFE_CLIENT_ID);
        const storedAuthuser = resolveCurrentAuthuser(scope);
        if (storedAuthuser && /^\d+$/.test(storedAuthuser) && storedAuthuser !== '0') {
            return storedAuthuser;
        }
    } catch {
        // Ignore localStorage access issues and keep base auth URL fallback.
    }
    return null;
};

const resolveAuthServerUrl = (): string => {
    const params = new URLSearchParams(window.location.search);
    const issuer = params.get('iss');
    const realmPath = `/realms/${IDSAFE_REALM}`;

    if (issuer) {
        try {
            const issuerUrl = new URL(issuer);
            const idx = issuerUrl.pathname.indexOf(realmPath);
            if (idx >= 0) {
                const authPath = issuerUrl.pathname.slice(0, idx);
                issuerUrl.pathname = authPath;
                issuerUrl.search = '';
                issuerUrl.hash = '';
                return normalizeAuthServerUrl(issuerUrl.toString());
            }
        } catch {
            // Ignore malformed issuer and fallback to authuser/base resolution.
        }
    }

    const authuser = params.get('authuser');
    if (authuser && /^\d+$/.test(authuser) && authuser !== '0') {
        return `${IDSAFE_BASE_AUTH_URL}/u/${authuser}`;
    }

    const storedAuthuser = resolveStoredAuthuser();
    if (storedAuthuser) {
        return `${IDSAFE_BASE_AUTH_URL}/u/${storedAuthuser}`;
    }

    return IDSAFE_BASE_AUTH_URL;
};

const keycloak = new Keycloak({
    url: resolveAuthServerUrl(),
    realm: IDSAFE_REALM,
    clientId: IDSAFE_CLIENT_ID,
});

// Log config for debugging
if (import.meta.env.DEV) {
    console.log('Keycloak config:', {
        url: keycloak.authServerUrl,
        realm: keycloak.realm,
        clientId: keycloak.clientId,
    });
}

export default keycloak;
