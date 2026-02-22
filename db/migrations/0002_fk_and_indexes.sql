BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'api_keys' AND column_name = 'user_id'
    ) THEN
        ALTER TABLE public.api_keys
            ALTER COLUMN user_id TYPE TEXT USING user_id::text;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'user_provider_keys' AND column_name = 'user_id'
    ) THEN
        ALTER TABLE public.user_provider_keys
            ALTER COLUMN user_id TYPE TEXT USING user_id::text;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'provider_key_logs' AND column_name = 'user_id'
    ) THEN
        ALTER TABLE public.provider_key_logs
            ALTER COLUMN user_id TYPE TEXT USING user_id::text;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'api_keys_user_id_fkey') THEN
        ALTER TABLE public.api_keys DROP CONSTRAINT api_keys_user_id_fkey;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_provider_keys_user_id_fkey') THEN
        ALTER TABLE public.user_provider_keys DROP CONSTRAINT user_provider_keys_user_id_fkey;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'provider_key_logs_user_id_fkey') THEN
        ALTER TABLE public.provider_key_logs DROP CONSTRAINT provider_key_logs_user_id_fkey;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'api_keys')
       AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'api_keys_user_id_gateway_users_fkey') THEN
        ALTER TABLE public.api_keys
            ADD CONSTRAINT api_keys_user_id_gateway_users_fkey
            FOREIGN KEY (user_id)
            REFERENCES public.gateway_users(idsafe_sub)
            ON UPDATE CASCADE
            ON DELETE CASCADE;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'user_provider_keys')
       AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_provider_keys_user_id_gateway_users_fkey') THEN
        ALTER TABLE public.user_provider_keys
            ADD CONSTRAINT user_provider_keys_user_id_gateway_users_fkey
            FOREIGN KEY (user_id)
            REFERENCES public.gateway_users(idsafe_sub)
            ON UPDATE CASCADE
            ON DELETE CASCADE;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'provider_key_logs')
       AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'provider_key_logs_user_id_gateway_users_fkey') THEN
        ALTER TABLE public.provider_key_logs
            ADD CONSTRAINT provider_key_logs_user_id_gateway_users_fkey
            FOREIGN KEY (user_id)
            REFERENCES public.gateway_users(idsafe_sub)
            ON UPDATE CASCADE
            ON DELETE CASCADE;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'api_keys') THEN
        CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON public.api_keys(user_id);
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'user_provider_keys') THEN
        CREATE INDEX IF NOT EXISTS idx_user_provider_keys_user_id ON public.user_provider_keys(user_id);
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'provider_key_logs') THEN
        CREATE INDEX IF NOT EXISTS idx_provider_key_logs_user_id ON public.provider_key_logs(user_id);
    END IF;
END $$;

COMMIT;
