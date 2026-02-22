BEGIN;

-- Seed from legacy auth.users if schema exists.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'auth' AND table_name = 'users'
    ) THEN
        INSERT INTO public.gateway_users (
            idsafe_sub,
            email,
            email_norm,
            vnpay_id,
            legacy_user_id,
            status,
            created_at,
            updated_at,
            last_login_at
        )
        SELECT
            u.id::text,
            u.email,
            lower(u.email),
            NULL,
            u.id,
            'active',
            COALESCE(u.created_at, now()),
            now(),
            u.last_sign_in_at
        FROM auth.users u
        ON CONFLICT (idsafe_sub)
        DO UPDATE SET
            email = COALESCE(EXCLUDED.email, gateway_users.email),
            email_norm = COALESCE(EXCLUDED.email_norm, gateway_users.email_norm),
            legacy_user_id = COALESCE(EXCLUDED.legacy_user_id, gateway_users.legacy_user_id),
            updated_at = now();
    END IF;
END $$;

-- Seed any orphan user_id found in business tables.
WITH all_user_ids AS (
    SELECT user_id FROM public.api_keys
    UNION
    SELECT user_id FROM public.user_provider_keys
    UNION
    SELECT user_id FROM public.provider_key_logs
)
INSERT INTO public.gateway_users (
    idsafe_sub,
    email,
    email_norm,
    vnpay_id,
    legacy_user_id,
    status,
    created_at,
    updated_at,
    last_login_at
)
SELECT
    au.user_id,
    NULL,
    NULL,
    NULL,
    CASE
        WHEN au.user_id ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
            THEN au.user_id::uuid
        ELSE NULL
    END,
    'active',
    now(),
    now(),
    NULL
FROM all_user_ids au
LEFT JOIN public.gateway_users gu ON gu.idsafe_sub = au.user_id
WHERE gu.idsafe_sub IS NULL;

COMMIT;
