## Skills

### Available skills
- deploy-compose-playwright: Deploy `ai_model_gateway` to Ubuntu via docker compose and verify with smoke + Playwright UI checks. (file: .agent/skills/deploy-compose-playwright/SKILL.md)

### How to use
- Trigger when the user asks to deploy/restart compose on server, run post-deploy verification, or execute UI checks after a fix.
- Prefer running `ops/deploy_remote_compose.sh` and `ops/smoke_after_deploy.sh` instead of ad-hoc commands.
