import Keycloak from 'keycloak-js';
import { getStorageScope, resolveCurrentAuthuser } from './keycloakMultiAccount';

/**
 * IDSafe (Keycloak) OIDC client for authentication.
 * Replaces Supabase Auth for user login/logout.
 */
const baseAuthUrl = (import.meta.env.VITE_IDSAFE_URL || 'https://sso.vnpay.dev').replace(/\/+$/, '');
const realm = import.meta.env.VITE_IDSAFE_REALM || 'idsafe-uat';
const clientId = import.meta.env.VITE_IDSAFE_CLIENT_ID || 'hyper-ai-gateway';

const normalizeAuthServerUrl = (candidate: string): string => candidate.replace(/\/+$/, '');

const resolveStoredAuthuser = (): string | null => {
    try {
        const scope = getStorageScope(realm, clientId);
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
    const realmPath = `/realms/${realm}`;

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
        return `${baseAuthUrl}/u/${authuser}`;
    }

    const storedAuthuser = resolveStoredAuthuser();
    if (storedAuthuser) {
        return `${baseAuthUrl}/u/${storedAuthuser}`;
    }

    return baseAuthUrl;
};

const keycloak = new Keycloak({
    url: resolveAuthServerUrl(),
    realm,
    clientId,
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
