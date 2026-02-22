BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.gateway_users (
    gateway_user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idsafe_sub TEXT NULL,
    email TEXT NULL,
    email_norm TEXT NULL,
    vnpay_id TEXT NULL,
    legacy_user_id UUID NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ NULL
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'gateway_users' AND column_name = 'gateway_user_id'
    ) THEN
        ALTER TABLE public.gateway_users ADD COLUMN gateway_user_id UUID;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'gateway_users' AND column_name = 'idsafe_sub'
    ) THEN
        ALTER TABLE public.gateway_users ADD COLUMN idsafe_sub TEXT NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'gateway_users' AND column_name = 'email'
    ) THEN
        ALTER TABLE public.gateway_users ADD COLUMN email TEXT NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'gateway_users' AND column_name = 'email_norm'
    ) THEN
        ALTER TABLE public.gateway_users ADD COLUMN email_norm TEXT NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'gateway_users' AND column_name = 'vnpay_id'
    ) THEN
        ALTER TABLE public.gateway_users ADD COLUMN vnpay_id TEXT NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'gateway_users' AND column_name = 'legacy_user_id'
    ) THEN
        ALTER TABLE public.gateway_users ADD COLUMN legacy_user_id UUID NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'gateway_users' AND column_name = 'status'
    ) THEN
        ALTER TABLE public.gateway_users ADD COLUMN status TEXT NOT NULL DEFAULT 'active';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'gateway_users' AND column_name = 'created_at'
    ) THEN
        ALTER TABLE public.gateway_users ADD COLUMN created_at TIMESTAMPTZ NOT NULL DEFAULT now();
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'gateway_users' AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE public.gateway_users ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'gateway_users' AND column_name = 'last_login_at'
    ) THEN
        ALTER TABLE public.gateway_users ADD COLUMN last_login_at TIMESTAMPTZ NULL;
    END IF;
END $$;

UPDATE public.gateway_users
SET gateway_user_id = gen_random_uuid()
WHERE gateway_user_id IS NULL;

DO $$
DECLARE
    pk_name TEXT;
    pk_is_gateway_user_id BOOLEAN := FALSE;
BEGIN
    SELECT c.conname,
           EXISTS (
               SELECT 1
               FROM unnest(c.conkey) AS k(attnum)
               JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
               WHERE a.attname = 'gateway_user_id'
           ) AND array_length(c.conkey, 1) = 1
    INTO pk_name, pk_is_gateway_user_id
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'public' AND t.relname = 'gateway_users' AND c.contype = 'p'
    LIMIT 1;

    IF pk_name IS NOT NULL AND NOT pk_is_gateway_user_id THEN
        -- If a previous deployment already created FKs against idsafe_sub via PK,
        -- drop them first so we can switch the PK to gateway_user_id.
        IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'api_keys_user_id_gateway_users_fkey') THEN
            ALTER TABLE public.api_keys DROP CONSTRAINT api_keys_user_id_gateway_users_fkey;
        END IF;
        IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_provider_keys_user_id_gateway_users_fkey') THEN
            ALTER TABLE public.user_provider_keys DROP CONSTRAINT user_provider_keys_user_id_gateway_users_fkey;
        END IF;
        IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'provider_key_logs_user_id_gateway_users_fkey') THEN
            ALTER TABLE public.provider_key_logs DROP CONSTRAINT provider_key_logs_user_id_gateway_users_fkey;
        END IF;

        EXECUTE format('ALTER TABLE public.gateway_users DROP CONSTRAINT %I', pk_name);
    END IF;
END $$;

ALTER TABLE public.gateway_users
    ALTER COLUMN gateway_user_id SET NOT NULL,
    ALTER COLUMN gateway_user_id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN idsafe_sub DROP NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'public'
          AND t.relname = 'gateway_users'
          AND c.contype = 'p'
          AND array_length(c.conkey, 1) = 1
          AND EXISTS (
              SELECT 1
              FROM unnest(c.conkey) AS k(attnum)
              JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
              WHERE a.attname = 'gateway_user_id'
          )
    ) THEN
        ALTER TABLE public.gateway_users
            ADD CONSTRAINT gateway_users_pkey PRIMARY KEY (gateway_user_id);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'gateway_users_idsafe_sub_key') THEN
        ALTER TABLE public.gateway_users
            ADD CONSTRAINT gateway_users_idsafe_sub_key UNIQUE (idsafe_sub);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'gateway_users_vnpay_id_key') THEN
        ALTER TABLE public.gateway_users
            ADD CONSTRAINT gateway_users_vnpay_id_key UNIQUE (vnpay_id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'gateway_users_legacy_user_id_key') THEN
        ALTER TABLE public.gateway_users
            ADD CONSTRAINT gateway_users_legacy_user_id_key UNIQUE (legacy_user_id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_gateway_users_email_norm ON public.gateway_users(email_norm);
CREATE INDEX IF NOT EXISTS idx_gateway_users_last_login_at ON public.gateway_users(last_login_at DESC);

CREATE TABLE IF NOT EXISTS public.gateway_user_conflicts (
    id BIGSERIAL PRIMARY KEY,
    conflict_type TEXT NOT NULL,
    idsafe_sub TEXT NULL,
    email_norm TEXT NULL,
    matched_subs TEXT[] NULL,
    details TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_gateway_user_conflicts_created_at
    ON public.gateway_user_conflicts(created_at DESC);

COMMIT;
