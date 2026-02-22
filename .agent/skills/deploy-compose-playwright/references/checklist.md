# Deploy and Test Checklist

## Deploy

1. Confirm target host, key path, stack dir.
2. Run `ops/deploy_remote_compose.sh`.
3. Confirm compose services are up and health check passed.

## Smoke

1. Run `ops/smoke_after_deploy.sh --base-url <public_url>`.
2. Verify frontend HTML loads.
3. Verify backend health status is `healthy`.
4. Verify `/docs` renders Swagger only when `CHECK_DOCS=true`.

## UI (Playwright/DevTools)

1. Open dashboard URL.
2. Confirm `TEST_USER_EMAIL` and `TEST_USER_PASSWORD` exist in `ops/.env`.
3. Login through IDSafe if redirected.
4. Verify landing dashboard visible (not blank/error state).
5. Open API key management page.
6. Create one key and confirm success toast.
7. Deactivate that key and confirm status changes.
8. Logout and verify unauthenticated view.

## Report format

1. Deploy: pass/fail + relevant command output summary.
2. Smoke: pass/fail + endpoint results.
3. UI: each scenario pass/fail + screenshot or error summary.
4. Risks/open issues: clear next action.
