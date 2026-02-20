import Keycloak from 'keycloak-js';

/**
 * IDSafe (Keycloak) OIDC client for authentication.
 * Replaces Supabase Auth for user login/logout.
 */
const keycloak = new Keycloak({
    url: import.meta.env.VITE_IDSAFE_URL || 'https://idsafe.vnpay.dev',
    realm: import.meta.env.VITE_IDSAFE_REALM || 'idsafe-uat',
    clientId: import.meta.env.VITE_IDSAFE_CLIENT_ID || 'hyper-ai-gateway',
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
