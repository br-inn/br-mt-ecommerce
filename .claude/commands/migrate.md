Run Alembic migrations for the mt-pricing-backend and restart the backend container.

Arguments (optional): `$ARGUMENTS`
- If empty: run `alembic upgrade head`
- If provided, treat as alembic target (e.g. `head`, `base`, `+1`, `-1`, or a specific revision)

Steps:
1. Run `./infra/scripts/migrate.sh upgrade $ARGUMENTS` (default target: `head`) from the project root using Bash
2. If the script succeeds, restart the backend: `docker restart mt-backend mt-worker mt-beat`
3. Verify with: `curl -s http://localhost:${CADDY_HTTP_PORT:-8081}/health/live`
4. Report: migration result + health check response

If migrate.sh fails, show the error and stop — do not restart containers.
