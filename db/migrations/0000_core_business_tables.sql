BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    name TEXT,
    key_prefix TEXT NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_api_keys_key_prefix ON public.api_keys(key_prefix);
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON public.api_keys(user_id);

CREATE TABLE IF NOT EXISTS public.user_provider_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    provider_name TEXT NOT NULL,
    api_key_encrypted TEXT NOT NULL,
    name TEXT,
    is_selected BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    disabled_until TIMESTAMPTZ NULL,
    CONSTRAINT user_provider_keys_provider_name_check CHECK (
        provider_name IN ('google', 'xai', 'gigachat', 'perplexity')
    )
);

CREATE INDEX IF NOT EXISTS idx_user_provider_keys_user_provider
    ON public.user_provider_keys(user_id, provider_name);
CREATE INDEX IF NOT EXISTS idx_user_provider_keys_user_selected
    ON public.user_provider_keys(user_id, is_selected)
    WHERE is_selected = TRUE;

CREATE TABLE IF NOT EXISTS public.provider_key_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    action TEXT NOT NULL,
    provider_name TEXT NOT NULL,
    key_id UUID NULL,
    description TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT provider_key_logs_action_check CHECK (
        action IN ('ADD', 'DELETE', 'SELECT', 'UNSELECT', 'IMPORT', 'FAILOVER_EXHAUSTED', 'RETRY_FAILED', 'ERROR')
    )
);

CREATE INDEX IF NOT EXISTS provider_key_logs_created_at_idx ON public.provider_key_logs(created_at);
CREATE INDEX IF NOT EXISTS provider_key_logs_user_id_idx ON public.provider_key_logs(user_id);

COMMIT;
