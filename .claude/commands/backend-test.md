Run the mt-pricing-backend pytest suite.

Arguments (optional): `$ARGUMENTS`
- If empty: run the full test suite
- If provided: treat as pytest path/filter (e.g. `tests/unit/services/matching`, `-k test_series_resolver`, `tests/unit -x`)

Steps:
1. Run pytest inside the backend container:
   ```
   docker exec mt-backend python -m pytest $ARGUMENTS -v --tb=short 2>&1
   ```
   If the container is not running, run directly:
   ```
   cd mt-pricing-backend && python -m pytest $ARGUMENTS -v --tb=short 2>&1
   ```
2. Summarize: total passed / failed / errors, and list any failing test names with their short traceback.
3. If all pass: confirm ✓. If any fail: show the failures clearly and suggest next steps.
