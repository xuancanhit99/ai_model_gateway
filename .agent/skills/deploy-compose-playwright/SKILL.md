---
name: deploy-compose-playwright
description: Deploy ai_model_gateway to Ubuntu server via docker compose down/up --build, then run smoke checks and UI verification with Playwright/DevTools.
---

# Deploy Compose + Playwright Skill

Use this skill when user asks to:

1. Deploy code to server stack `/opt/stacks/ai_model_gateway`
2. Restart services with `docker compose down` and `docker compose up -d --build`
3. Verify app after deploy by smoke checks and UI checks

## Workflow

1. Run deploy script:
   - `ops/deploy_remote_compose.sh`
2. Run smoke checks:
   - `ops/smoke_after_deploy.sh`
3. Run UI validation with MCP Playwright/DevTools:
   - open dashboard URL
   - verify login flow using `TEST_USER_EMAIL` and `TEST_USER_PASSWORD` from `ops/.env`
   - verify API key list screen renders
   - execute one key action (create or activate/deactivate)
4. Report:
   - deploy status
   - smoke status
   - UI test status
   - blockers and next actions

## Commands

From `ai_model_gateway` directory:

```bash
cp ops/.env.example ops/.env
./ops/deploy_remote_compose.sh
./ops/smoke_after_deploy.sh
```

To run authenticated UI flow, ensure these are set in `ops/.env`:

```bash
TEST_USER_EMAIL=...
TEST_USER_PASSWORD=...
# Optional
TEST_USER_OTP=...
```

If remote stack does not pull from git, sync local files first:

```bash
./ops/deploy_remote_compose.sh --deploy-mode rsync
```

## References

Read this first for full checklist:

- `references/checklist.md`
- `../../../../ops/CODEX_DEV_DEPLOY_TEST_WORKFLOW.md`
