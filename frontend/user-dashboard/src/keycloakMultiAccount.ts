const STORAGE_PREFIX = 'kc_multi_account_v1';
const AUTHUSER_PARAM = 'authuser';
const DEFAULT_AUTHUSER = '0';
const CALLBACK_PREFIX = 'kc-callback-';
const LEGACY_KEYS = ['kc_token', 'kc_refreshToken', 'kc_idToken'];
const UNKNOWN_SCOPE = 'unknown-realm:unknown-client';

export interface StoredKeycloakSession {
  token: string;
  refreshToken?: string;
  idToken?: string;
  sub: string;
  authuser: string;
  savedAt: number;
}

export interface StoredSessionLookup {
  key: string;
  session: StoredKeycloakSession;
}

const normalizeAuthuser = (value: string | null | undefined): string => {
  if (!value) {
    return DEFAULT_AUTHUSER;
  }

  return /^\d+$/.test(value) ? value : DEFAULT_AUTHUSER;
};

export const getStorageScope = (realm: string | undefined, clientId: string | undefined): string => {
  return `${realm || 'unknown-realm'}:${clientId || 'unknown-client'}`;
};

const keyActiveAuthuser = (scope: string): string => `${STORAGE_PREFIX}:${scope}:active-authuser`;
const keyActiveSub = (scope: string, authuser: string): string => `${STORAGE_PREFIX}:${scope}:active-sub:${authuser}`;
const keySessionPrefix = (scope: string, authuser: string): string => `${STORAGE_PREFIX}:${scope}:session:${authuser}:`;
const keySkipRestore = (scope: string): string => `${STORAGE_PREFIX}:${scope}:skip-restore-once`;

const buildSessionKey = (scope: string, authuser: string, sub: string): string => {
  return `${keySessionPrefix(scope, authuser)}${sub}`;
};

export const readAuthuserFromUrl = (): string | null => {
  const params = new URLSearchParams(window.location.search);
  if (!params.has(AUTHUSER_PARAM)) {
    return null;
  }
  return normalizeAuthuser(params.get(AUTHUSER_PARAM));
};

export const resolveCurrentAuthuser = (scope: string): string => {
  const fromUrl = readAuthuserFromUrl();
  if (fromUrl) {
    return fromUrl;
  }

  return normalizeAuthuser(localStorage.getItem(keyActiveAuthuser(scope)));
};

export const rememberActiveAuthuser = (scope: string, authuser: string): void => {
  localStorage.setItem(keyActiveAuthuser(scope), normalizeAuthuser(authuser));
};

export const buildRedirectUri = (authuser?: string | null): string => {
  const redirectUrl = new URL(`${window.location.origin}${window.location.pathname}`);
  if (authuser !== null && authuser !== undefined) {
    const normalized = normalizeAuthuser(authuser);
    redirectUrl.searchParams.set(AUTHUSER_PARAM, normalized);
  }

  return redirectUrl.toString();
};

export const patchPkceCallbackRedirectUri = (redirectUri: string): void => {
  try {
    const params = new URLSearchParams(window.location.search);
    const state = params.get('state');
    const code = params.get('code');
    if (!state || !code) {
      return;
    }

    const storageKey = `${CALLBACK_PREFIX}${state}`;
    const raw = localStorage.getItem(storageKey);
    if (!raw) {
      return;
    }

    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const encodedStoredRedirectUri = parsed.redirectUri;
    if (typeof encodedStoredRedirectUri !== 'string' || !encodedStoredRedirectUri) {
      return;
    }

    const storedRedirectUri = decodeURIComponent(encodedStoredRedirectUri);
    if (storedRedirectUri === redirectUri) {
      return;
    }

    // keycloak-js expects redirectUri in callback storage as raw URL, not URI-encoded.
    parsed.redirectUri = redirectUri;
    const loginOptions = parsed.loginOptions;
    if (loginOptions && typeof loginOptions === 'object') {
      (loginOptions as Record<string, unknown>).redirectUri = redirectUri;
    }

    localStorage.setItem(storageKey, JSON.stringify(parsed));
  } catch (error) {
    console.warn('Unable to patch Keycloak callback redirect URI', error);
  }
};

const parseStoredSession = (raw: string | null): StoredKeycloakSession | null => {
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as Partial<StoredKeycloakSession>;
    if (!parsed.token || !parsed.sub || !parsed.authuser) {
      return null;
    }

    return {
      token: parsed.token,
      refreshToken: parsed.refreshToken,
      idToken: parsed.idToken,
      sub: parsed.sub,
      authuser: normalizeAuthuser(parsed.authuser),
      savedAt: typeof parsed.savedAt === 'number' ? parsed.savedAt : 0,
    };
  } catch {
    return null;
  }
};

const listStoredSessionKeys = (scope: string, authuser: string): string[] => {
  const prefix = keySessionPrefix(scope, authuser);
  const keys: string[] = [];

  for (let i = 0; i < localStorage.length; i += 1) {
    const key = localStorage.key(i);
    if (key && key.startsWith(prefix)) {
      keys.push(key);
    }
  }

  return keys;
};

export const saveStoredSession = (
  scope: string,
  authuser: string,
  input: {
    token?: string;
    refreshToken?: string;
    idToken?: string;
    sub?: string;
  },
): void => {
  if (!input.token || !input.refreshToken || !input.sub) {
    return;
  }

  const normalizedAuthuser = normalizeAuthuser(authuser);
  const payload: StoredKeycloakSession = {
    token: input.token,
    refreshToken: input.refreshToken,
    idToken: input.idToken,
    sub: input.sub,
    authuser: normalizedAuthuser,
    savedAt: Date.now(),
  };

  localStorage.setItem(buildSessionKey(scope, normalizedAuthuser, payload.sub), JSON.stringify(payload));
  localStorage.setItem(keyActiveSub(scope, normalizedAuthuser), payload.sub);
  rememberActiveAuthuser(scope, normalizedAuthuser);
};

export const restoreStoredSessionForAuthuser = (scope: string, authuser: string): StoredSessionLookup | null => {
  const normalizedAuthuser = normalizeAuthuser(authuser);
  const activeSub = localStorage.getItem(keyActiveSub(scope, normalizedAuthuser));

  if (activeSub) {
    const activeKey = buildSessionKey(scope, normalizedAuthuser, activeSub);
    const activeSession = parseStoredSession(localStorage.getItem(activeKey));
    if (activeSession) {
      return { key: activeKey, session: activeSession };
    }
  }

  let latestLookup: StoredSessionLookup | null = null;

  for (const key of listStoredSessionKeys(scope, normalizedAuthuser)) {
    const session = parseStoredSession(localStorage.getItem(key));
    if (!session) {
      continue;
    }

    if (!latestLookup || session.savedAt > latestLookup.session.savedAt) {
      latestLookup = { key, session };
    }
  }

  return latestLookup;
};

export const clearStoredSessionLookup = (scope: string, lookup: StoredSessionLookup): void => {
  localStorage.removeItem(lookup.key);

  const normalizedAuthuser = normalizeAuthuser(lookup.session.authuser);
  const activeSubKey = keyActiveSub(scope, normalizedAuthuser);
  if (localStorage.getItem(activeSubKey) === lookup.session.sub) {
    localStorage.removeItem(activeSubKey);
  }
};

export const clearStoredSessionsForAuthuser = (scope: string, authuser: string): void => {
  const normalizedAuthuser = normalizeAuthuser(authuser);
  localStorage.removeItem(keyActiveSub(scope, normalizedAuthuser));

  for (const key of listStoredSessionKeys(scope, normalizedAuthuser)) {
    localStorage.removeItem(key);
  }
};

export const clearLegacyKeycloakTokens = (): void => {
  for (const key of LEGACY_KEYS) {
    localStorage.removeItem(key);
  }
};

export const cleanupUnknownScopeStorage = (activeScope: string): void => {
  if (activeScope === UNKNOWN_SCOPE) {
    return;
  }

  const unknownPrefix = `${STORAGE_PREFIX}:${UNKNOWN_SCOPE}:`;
  const toDelete: string[] = [];

  for (let i = 0; i < localStorage.length; i += 1) {
    const key = localStorage.key(i);
    if (key && key.startsWith(unknownPrefix)) {
      toDelete.push(key);
    }
  }

  for (const key of toDelete) {
    localStorage.removeItem(key);
  }
};

export const markSkipRestoreOnce = (scope: string): void => {
  localStorage.setItem(keySkipRestore(scope), '1');
};

export const consumeSkipRestoreOnce = (scope: string): boolean => {
  if (localStorage.getItem(keySkipRestore(scope)) !== '1') {
    return false;
  }

  localStorage.removeItem(keySkipRestore(scope));
  return true;
};
